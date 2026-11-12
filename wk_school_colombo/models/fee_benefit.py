# -*- coding: utf-8 -*-
"""Adaptador ligero de beneficios/descuentos y cupones (tarea 11856, 2.13).

Decisión explícita del usuario (no replicar el motor completo de
sale_loyalty, acoplado a sale.order): se reutiliza el catálogo estándar de
Odoo (loyalty.program/rule/reward/card, que no depende de sale.order) pero el
cálculo del descuento es una lógica propia, simple, que solo soporta
recompensas de tipo "Descuento" en modo porcentaje o monto fijo por recibo
-no productos gratis, ni "por punto", ni combinación de varias recompensas-.
El beneficio se aplica como una línea independiente y negativa del recibo de
tarifa (wk.fee.slip.lines), el mismo patrón que ya usa la pestaña "Resumen de
tarifas" para la cuota de biblioteca (confirm_fee_slip, fee_slip.py) y que el
propio requerimiento permite explícitamente ("el descuento podrá
representarse como una línea independiente... siguiendo el comportamiento
estándar de Odoo").
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FeeDiscountLog(models.Model):
    _name = 'wk.fee.discount.log'
    _description = 'Registro de beneficios/descuentos aplicados a un recibo de tarifa'
    _order = 'create_date desc'

    fee_slip_id = fields.Many2one(
        'wk.fee.slip', string='Recibo de tarifa', required=True, ondelete='cascade')
    enrollment_id = fields.Many2one(
        related='fee_slip_id.enrollment_id', store=True, string='Inscripción')
    tipo = fields.Selection([
        ('manual', 'Descuento manual'),
        ('loyalty', 'Beneficio / cupón'),
    ], string='Tipo', required=True)
    program_id = fields.Many2one('loyalty.program', string='Programa')
    reward_id = fields.Many2one('loyalty.reward', string='Recompensa')
    card_id = fields.Many2one('loyalty.card', string='Cupón/Tarjeta')
    codigo = fields.Char(string='Código')
    currency_id = fields.Many2one(related='fee_slip_id.currency_id', string='Moneda')
    monto = fields.Monetary(string='Valor descontado', currency_field='currency_id')
    user_id = fields.Many2one(
        'res.users', string='Usuario', default=lambda self: self.env.user)
    motivo = fields.Char(string='Motivo/Nota')


class FeeSlipLine(models.Model):
    """Concepto propio de la línea, independiente del nombre del producto.

    Sin esto, una línea de beneficio/cupón (apply_benefit, abajo) solo podía
    mostrar el nombre del producto fijo usado como "concepto de descuento"
    (_get_discount_product) -el mismo producto para TODOS los beneficios,
    sin distinguir cuál programa/cupón se aplicó-. Queda vacío para líneas
    normales (creadas por wk_school_management, que nunca pasan 'name') y
    las pantallas que lo muestran deben caer a product_id.display_name en
    ese caso (mismo criterio que 'name' en account.move.line/sale.order.line
    frente a su product_id).
    """

    _inherit = 'wk.fee.slip.lines'

    name = fields.Char(string='Concepto')


class FeeBenefit(models.AbstractModel):
    _name = 'wk.fee.benefit'
    _description = 'Adaptador ligero de beneficios/cupones sobre un recibo de tarifa'

    @api.model
    def _get_discount_product(self):
        product = self.env['product.product'].search(
            [('is_benefit_discount_element', '=', True)], limit=1)
        if not product:
            raise UserError(_(
                'No hay ningún producto marcado como "¿Es concepto de '
                'descuento/beneficio?" (Configuración > Productos). Cree uno '
                'o marque uno existente antes de aplicar un beneficio.'))
        return product

    @api.model
    def _compute_benefit(self, code, base_lines, total_amount):
        """Calcula, SIN escribir nada, el descuento que daría el código
        ``code`` sobre ``base_lines`` (lista de ``(product, fee)`` con las
        líneas "reales" del recibo, positivas y sin descuentos) cuyo total es
        ``total_amount``. Lo comparten ``apply_benefit`` (aplica sobre un recibo
        ya creado) y el wizard "Generar recibos de tarifas" (muestra el
        descuento antes de crear el recibo, para que la tabla de cuotas se
        arme sobre el valor neto).

        Devuelve ``{'rule', 'program', 'reward', 'amount'}``.
        """
        rule = self.env['loyalty.rule'].search([
            ('mode', '=', 'with_code'), ('code', '=', code), ('active', '=', True),
        ], limit=1)
        if not rule:
            raise UserError(_('El código "%s" no corresponde a ningún beneficio activo.', code))

        program = rule.program_id
        reward = program.reward_ids.filtered(lambda r: r.reward_type == 'discount')[:1]
        if not reward:
            raise UserError(_(
                'El programa "%s" no tiene configurada una recompensa de tipo '
                'descuento; esta integración no soporta productos gratis.',
                program.name))

        # La regla del programa (como en ventas) solo se cumple si el recibo
        # tiene alguno de los productos de la regla.
        rule_domain = rule._get_valid_product_domain()
        rule_lines = [
            (product, fee) for product, fee in base_lines
            if product.filtered_domain(rule_domain)]
        if not rule_lines:
            raise UserError(_(
                'El beneficio "%s" no aplica: el recibo no tiene ninguno de '
                'los productos requeridos por la regla del programa.',
                program.name))

        # Productos/líneas sobre los que la recompensa permite descontar.
        if reward.discount_applicability == 'specific':
            reward_domain = reward._get_discount_product_domain()
            discountable = [
                (product, fee) for product, fee in base_lines
                if product.filtered_domain(reward_domain)]
            if not discountable:
                raise UserError(_(
                    'El descuento "%s" solo aplica a productos específicos y '
                    'ninguno de los conceptos de este recibo está entre ellos.',
                    reward.description or program.name))
        elif reward.discount_applicability == 'cheapest':
            discountable = sorted(base_lines, key=lambda l: l[1])[:1]
        else:
            discountable = list(base_lines)
        total = sum(fee for _product, fee in discountable)

        if rule.minimum_amount and total_amount < rule.minimum_amount:
            raise UserError(_(
                'El beneficio "%(program)s" exige un monto mínimo de %(minimo)s.',
                program=program.name, minimo=rule.minimum_amount))

        if reward.discount_mode == 'percent':
            amount = total * reward.discount / 100.0
        elif reward.discount_mode == 'per_order':
            amount = reward.discount
        else:
            raise UserError(_(
                'El modo de descuento de "%s" (por punto) no está soportado '
                'por esta integración ligera de beneficios.', reward.description))

        if reward.discount_max_amount:
            amount = min(amount, reward.discount_max_amount)
        amount = min(amount, total)
        return {'rule': rule, 'program': program, 'reward': reward, 'amount': amount}

    @api.model
    def apply_benefit(self, fee_slip, code):
        """Aplica, sobre ``fee_slip`` (un wk.fee.slip ya con sus líneas de
        fee pero SIN facturar todavía), el beneficio/cupón identificado por
        ``code``. Devuelve el monto descontado.
        """
        fee_slip.ensure_one()
        # Ronda de ajustes post-prueba: sin este guard, volver a pulsar
        # "Aplicar" (p. ej. porque la pantalla de "Resumen de tarifas" de la
        # Inscripción no muestra ningún cambio visible -el descuento vive en
        # las líneas del recibo, no en el catálogo fee_summary_ids-) vuelve a
        # calcular el % de descuento sobre el total YA descontado y lo
        # descuenta otra vez, encima del anterior (descuento compuesto en
        # vez de un único descuento sobre el valor original).
        if self.env['wk.fee.discount.log'].search_count([
                ('fee_slip_id', '=', fee_slip.id), ('tipo', '=', 'loyalty')]):
            raise UserError(_(
                'Este recibo ya tiene un beneficio/cupón aplicado; no se '
                'puede aplicar más de uno.'))

        # Solo las líneas "reales" del recibo (positivas, sin descuentos).
        base_lines = fee_slip.fee_slip_line_ids.filtered(lambda l: l.fee > 0)
        result = self._compute_benefit(
            code, [(l.product_id, l.fee) for l in base_lines], fee_slip.total_amount)
        program, reward, amount = result['program'], result['reward'], result['amount']

        card = self.env['loyalty.card']
        if program.program_type == 'loyalty':
            partner = fee_slip._get_fee_invoice_partner()
            card = self.env['loyalty.card'].search([
                ('program_id', '=', program.id),
                ('partner_id', '=', partner.id),
                ('active', '=', True),
            ], limit=1)
            if not card or card.points < reward.required_points:
                raise UserError(_(
                    'El estudiante no tiene puntos suficientes en el programa '
                    '"%s" para este beneficio.', program.name))

        if card and reward.required_points:
            card.points -= reward.required_points

        # Igual que en ventas: producto de descuento propio de la recompensa y
        # "Descripción en la orden" como texto de la línea (no un producto del
        # catálogo de cursos, que movería la contabilidad/centro de costos).
        product = reward.discount_line_product_id or self._get_discount_product()
        self.env['wk.fee.slip.lines'].create({
            'fee_slip_id': fee_slip.id,
            'product_id': product.id,
            'name': reward.description or program.name,
            'fee': -amount,
        })

        self.env['wk.fee.discount.log'].create({
            'fee_slip_id': fee_slip.id,
            'tipo': 'loyalty',
            'program_id': program.id,
            'reward_id': reward.id,
            'card_id': card.id if card else False,
            'codigo': code,
            'monto': amount,
            'motivo': _('Aplicado desde "Generar recibos de tarifas"'),
        })
        return amount
