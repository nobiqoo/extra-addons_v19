# -*- coding: utf-8 -*-
from odoo import api, models, fields


class FeeSummary(models.Model):
    """Linea del resumen de tarifas de la inscripcion (tarea 11293).

    Se reutiliza la funcionalidad estandar de listas de precios de Odoo: la
    linea guarda la lista aplicable y, cuando esa lista define una regla para
    el concepto de cobro, la tarifa se toma de ahi. Si la lista no tiene regla
    para el producto se conserva el valor que traia la linea (el configurado en
    la estructura de tarifas), para no alterar los importes de las
    inscripciones que ya se gestionan asi.

    La lista se propone desde el contacto del estudiante y queda editable en la
    inscripcion; cambiarla aqui nunca modifica la lista del contacto.
    """

    _inherit = 'wk.fee.summary'

    pricelist_id = fields.Many2one(
        'product.pricelist',
        string="Lista de precios",
        ondelete='restrict',
        help="Lista de precios con la que se valora el concepto de cobro. Se "
             "propone la del contacto del estudiante y puede cambiarse solo "
             "para esta inscripción.")

    fee_before_discount = fields.Float(
        string="Tarifa antes de descuento", readonly=True,
        help="Tarifa resultante de la lista de precios/estructura, antes de "
             "aplicar el % Descuento. Solo de consulta/trazabilidad: 'fee' "
             "ya queda neto de descuento y es el valor que usa el resto del "
             "módulo (total de la inscripción, generación de recibos, "
             "factura).")
    discount_percent = fields.Float(
        string="% Descuento", default=0.0,
        help="Porcentaje de descuento aplicado sobre este concepto de cobro. "
             "Disminuye 'Tarifa' (fee); el monto ajustado es la base para la "
             "factura y, si aplica pago por cuotas, para la tabla de "
             "amortización.")
    discount_amount = fields.Float(
        string="Valor descuento", compute='_compute_discount_amount')

    @api.depends('fee_before_discount', 'discount_percent')
    def _compute_discount_amount(self):
        for line in self:
            line.discount_amount = line.fee_before_discount * (line.discount_percent or 0.0) / 100.0

    def _get_pricelist_fee(self, fee_structure=None):
        """Precio del concepto según la lista, o None si la lista no lo define.

        Se consulta primero la regla (``_get_product_rule``) porque sin regla
        aplicable la lista devuelve el precio de venta del producto, y en ese
        caso la tarifa debe seguir siendo la de la estructura de tarifas.
        """
        self.ensure_one()
        if not self.pricelist_id or not self.product_id:
            return None
        structure = fee_structure or self.enrollment_id.fee_structure_id
        currency = self.enrollment_id.currency_id or structure.currency_id or None
        if not self.pricelist_id._get_product_rule(
                self.product_id, 1.0, currency=currency):
            return None
        return self.pricelist_id._get_product_price(
            self.product_id, 1.0, currency=currency)

    def _get_base_fee(self, fee_structure=None):
        """Tarifa de referencia cuando la lista no define precio.

        Es la del componente de la estructura de tarifas y, si el concepto no
        está en la estructura (líneas agregadas a mano), el precio de venta del
        producto, que es lo que aplica hoy el módulo.
        """
        self.ensure_one()
        if not self.product_id:
            return None
        structure = fee_structure or self.enrollment_id.fee_structure_id
        component = structure.fee_component_ids.filtered(
            lambda c: c.product_id == self.product_id)[:1]
        return component.fee if component else self.product_id.lst_price

    def _apply_pricelist_fee(self, fee_structure=None):
        """Recalcula la tarifa con la lista actual de la línea.

        Con regla en la lista manda ese precio; sin regla se vuelve a la tarifa
        de referencia, para que quitar o cambiar la lista deshaga el precio
        especial en lugar de dejar el anterior congelado. El % Descuento ya
        definido en la línea se vuelve a aplicar sobre el nuevo valor (tarea
        11856): cambiar de lista de precios no debe hacer que el descuento se
        pierda silenciosamente.
        """
        for line in self:
            fee = line._get_pricelist_fee(fee_structure)
            if fee is None:
                fee = line._get_base_fee(fee_structure)
            if fee is not None:
                line.fee_before_discount = fee
                line._apply_discount()

    def _apply_discount(self):
        """Recalcula 'fee' (neto) a partir de fee_before_discount y % Descuento."""
        for line in self:
            line.fee = line.fee_before_discount * (1 - (line.discount_percent or 0.0) / 100.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        # El original deja la tarifa en el precio de venta del producto; si la
        # lista tiene un precio propio para ese producto, ese es el que manda.
        super()._onchange_product_id()
        self._apply_pricelist_fee()

    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        self._apply_pricelist_fee()

    @api.onchange('discount_percent')
    def _onchange_discount_percent(self):
        for line in self:
            if not line.fee_before_discount and line.fee:
                # Linea creada por codigo sin pasar por _apply_pricelist_fee:
                # el 'fee' actual es la referencia, no hay otro dato mejor.
                line.fee_before_discount = line.fee
        self._apply_discount()

    def write(self, vals):
        """Reaplica el % Descuento cuando se escribe por código/ORM.

        _onchange_discount_percent solo corre en el formulario; sin este
        override, escribir discount_percent desde un server action, un
        import o cualquier llamada directa a write() no recalculaba 'fee'
        en absoluto (detectado en la verificación funcional de la tarea
        11856).
        """
        res = super().write(vals)
        if 'discount_percent' in vals or 'fee_before_discount' in vals:
            for line in self:
                if not line.fee_before_discount and line.fee:
                    line.fee_before_discount = line.fee
            self._apply_discount()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Completa la lista de precios en las líneas creadas desde código.

        Solo rellena el campo cuando no viene informado; la tarifa no se toca
        aquí para no reinterpretar importes que el llamador ya calculó (las
        líneas creadas desde el formulario ya pasaron por los onchange).
        """
        # Solo se consideran los ids enteros: wk_school_management arma estos
        # diccionarios con recordsets en algunos flujos y browse() fallaria.
        enrollments = self.env['student.enrollment'].browse([
            vals['enrollment_id'] for vals in vals_list
            if isinstance(vals.get('enrollment_id'), int)
            and not vals.get('pricelist_id')])
        pricelists = {
            enrollment.id: enrollment._get_student_pricelist().id
            for enrollment in enrollments}
        for vals in vals_list:
            if not vals.get('pricelist_id'):
                pricelist_id = pricelists.get(vals.get('enrollment_id'))
                if pricelist_id:
                    vals['pricelist_id'] = pricelist_id
            if not vals.get('fee_before_discount') and vals.get('fee'):
                # Referencia de auditoria para lineas creadas desde codigo sin
                # pasar por el onchange (p.ej. al generar desde la estructura
                # de tarifas): sin otro dato mejor, el propio 'fee' es la base.
                vals['fee_before_discount'] = vals['fee']
            if vals.get('discount_percent'):
                # Crear la línea ya con discount_percent informado (p.ej.
                # desde código) debe dejar 'fee' neta desde el principio, no
                # solo cuando después se edite por el formulario.
                vals['fee'] = vals['fee_before_discount'] * (1 - vals['discount_percent'] / 100.0)
        return super().create(vals_list)
