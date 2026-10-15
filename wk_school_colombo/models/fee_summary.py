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
        especial en lugar de dejar el anterior congelado.
        """
        for line in self:
            fee = line._get_pricelist_fee(fee_structure)
            if fee is None:
                fee = line._get_base_fee(fee_structure)
            if fee is not None:
                line.fee = fee

    @api.onchange('product_id')
    def _onchange_product_id(self):
        # El original deja la tarifa en el precio de venta del producto; si la
        # lista tiene un precio propio para ese producto, ese es el que manda.
        super()._onchange_product_id()
        self._apply_pricelist_fee()

    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        self._apply_pricelist_fee()

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
        return super().create(vals_list)
