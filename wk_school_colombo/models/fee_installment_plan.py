# -*- coding: utf-8 -*-
"""Tabla de amortizacion del pago por cuotas (tarea 11856).

Un wk.fee.installment.plan agrupa el acuerdo de pago de UN wk.fee.slip (y por
lo tanto de UNA sola factura, nunca varias). Cada wk.fee.installment.line es
una cuota congelada (fecha y valor originalmente programados no cambian)
enlazada a la linea contable especifica (account.move.line, display_type
'payment_term') que Odoo genero para esa fecha de vencimiento dentro del
termino de pago personalizado del acuerdo. Pagado/Saldo/Estado se leen en vivo
desde esa linea contable: no se duplica ningun movimiento contable propio.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FeeInstallmentPlan(models.Model):
    _name = 'wk.fee.installment.plan'
    _description = 'Acuerdo de pago por cuotas'

    enrollment_id = fields.Many2one(
        'student.enrollment', string='Inscripción', required=True,
        ondelete='cascade', index=True)
    fee_slip_id = fields.Many2one(
        'wk.fee.slip', string='Recibo de tarifa', required=True,
        ondelete='cascade', index=True)
    invoice_id = fields.Many2one(
        'account.move', string='Factura',
        compute='_compute_invoice_id', store=True)
    currency_id = fields.Many2one(
        related='fee_slip_id.currency_id', string='Moneda')
    monto_total = fields.Float(
        string='Monto total a pagar', related='fee_slip_id.total_amount')
    monto_inicial = fields.Monetary(string='Monto inicial', currency_field='currency_id')
    numero_abonos = fields.Integer(string='Número de abonos')
    periodicidad = fields.Selection([
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
    ], string='Periodicidad', default='mensual')
    line_ids = fields.One2many(
        'wk.fee.installment.line', 'plan_id', string='Cuotas')

    saldo_pendiente_total = fields.Monetary(
        string='Saldo pendiente', compute='_compute_resumen',
        currency_field='currency_id', store=True)
    cuotas_pagadas = fields.Integer(string='Cuotas pagadas', compute='_compute_resumen', store=True)
    cuotas_pendientes = fields.Integer(string='Cuotas pendientes', compute='_compute_resumen', store=True)
    proxima_fecha_vencimiento = fields.Date(
        string='Próxima fecha de vencimiento', compute='_compute_resumen', store=True)
    proximo_valor_abono = fields.Monetary(
        string='Valor del próximo abono', compute='_compute_resumen',
        currency_field='currency_id', store=True)
    estado_acuerdo = fields.Selection([
        ('al_dia', 'Al día'),
        ('pendiente', 'Con cuotas pendientes'),
        ('mora', 'En mora'),
    ], string='Estado del acuerdo', compute='_compute_resumen', store=True)

    @api.depends('fee_slip_id.invoice_ids')
    def _compute_invoice_id(self):
        for plan in self:
            plan.invoice_id = plan.fee_slip_id.invoice_ids[:1]

    @api.depends(
        'line_ids.estado', 'line_ids.saldo', 'line_ids.fecha_vencimiento',
        'line_ids.valor_programado')
    def _compute_resumen(self):
        for plan in self:
            lines = plan.line_ids.sorted('fecha_vencimiento')
            pendientes = lines.filtered(lambda l: l.estado in ('pendiente', 'parcial', 'mora'))
            plan.saldo_pendiente_total = sum(lines.mapped('saldo'))
            plan.cuotas_pagadas = len(lines) - len(pendientes)
            plan.cuotas_pendientes = len(pendientes)
            next_line = pendientes[:1]
            plan.proxima_fecha_vencimiento = next_line.fecha_vencimiento if next_line else False
            plan.proximo_valor_abono = next_line.saldo if next_line else 0.0
            if lines.filtered(lambda l: l.estado == 'mora'):
                plan.estado_acuerdo = 'mora'
            elif pendientes:
                plan.estado_acuerdo = 'pendiente'
            else:
                plan.estado_acuerdo = 'al_dia'


class FeeInstallmentLine(models.Model):
    _name = 'wk.fee.installment.line'
    _description = 'Cuota de la tabla de amortización'
    _order = 'fecha_vencimiento asc'

    plan_id = fields.Many2one(
        'wk.fee.installment.plan', string='Acuerdo de pago',
        required=True, ondelete='cascade', index=True)
    enrollment_id = fields.Many2one(
        related='plan_id.enrollment_id', store=True, string='Inscripción',
        help="Related almacenado: permite exponer la tabla de amortización "
             "como un One2many directo en student.enrollment (pestaña "
             "Resumen de tarifas) sin otra relación intermedia.")
    sequence = fields.Integer(string='#', default=10)
    name = fields.Char(string='Cuota', required=True)
    fecha_vencimiento = fields.Date(string='Fecha de vencimiento', required=True)
    valor_programado = fields.Monetary(
        string='Valor programado', required=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Moneda')
    move_line_id = fields.Many2one(
        'account.move.line', string='Línea contable (vencimiento)',
        ondelete='restrict')
    invoice_id = fields.Many2one(
        related='plan_id.invoice_id', string='Factura', store=True)

    valor_pagado = fields.Monetary(
        string='Valor pagado', compute='_compute_estado_pago', store=True,
        currency_field='currency_id')
    saldo = fields.Monetary(
        string='Saldo', compute='_compute_estado_pago', store=True,
        currency_field='currency_id')
    estado = fields.Selection([
        ('pendiente', 'Pendiente'),
        ('parcial', 'Pago parcial'),
        ('pagado', 'Pagado'),
        ('mora', 'En mora'),
    ], string='Estado', compute='_compute_estado_pago', store=True)

    @api.depends(
        'move_line_id.amount_residual_currency', 'move_line_id.reconciled',
        'valor_programado', 'fecha_vencimiento')
    def _compute_estado_pago(self):
        today = fields.Date.context_today(self)
        for line in self:
            residual = line.move_line_id.amount_residual_currency if line.move_line_id else line.valor_programado
            currency = line.currency_id
            if currency and currency.is_zero(residual):
                residual = 0.0
            residual = max(0.0, residual)
            line.saldo = residual
            line.valor_pagado = max(0.0, line.valor_programado - residual)
            if residual <= 0.0:
                line.estado = 'pagado'
            elif line.fecha_vencimiento and line.fecha_vencimiento < today:
                line.estado = 'mora'
            elif line.valor_pagado > 0.0:
                line.estado = 'parcial'
            else:
                line.estado = 'pendiente'

    def action_registrar_abono(self):
        self.ensure_one()
        return self.move_line_id.action_register_payment()

    def action_ver_pago(self):
        self.ensure_one()
        # payment_id vive en account.move.line, no en account.move -no hace
        # falta (ni se puede) saltar con .move_id: credit_move_id/
        # debit_move_id ya son las lineas contables conciliadas.
        payments = (
            self.move_line_id.matched_credit_ids.credit_move_id
            + self.move_line_id.matched_debit_ids.debit_move_id
        ).payment_id
        # (False, 'form')/(False, 'list') -en vez de pisar "views" de una
        # accion prestada con _for_xml_id- deja que Odoo resuelva sus
        # propias vistas por defecto para account.payment; con un unico
        # pago, "res_id" + view_mode empezando por 'list' ya abre
        # directamente el formulario (mismo comportamiento estandar que
        # usa el resto del modulo, ver wk_action_register_installment_payment
        # en account_move_line.py).
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pagos'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'res_id': payments.id if len(payments) == 1 else False,
            'domain': [('id', 'in', payments.ids)],
        }

    def action_imprimir_tirilla(self):
        """Tarea 12458 / incidencia PT12445: tirilla del pago reconciliado
        con ESTA cuota.

        Lo único que se exige es que la cuota esté pagada -da igual cómo se
        haya registrado el pago (wizard "Registrar Pago", extracto
        bancario, asiento manual en un diario de caja/banco, etc.); ver
        account.move.line._wk_tirilla_docs(). Una cuota puede tener más de
        un pago reconciliado (p.ej. un abono parcial seguido de otro que la
        completa); en ese caso se imprime una tirilla por cada uno, nunca
        una combinada, porque cada documento ya es la unidad atómica de
        trazabilidad (2.9).
        """
        self.ensure_one()
        if self.estado != 'pagado':
            raise UserError(_(
                "Esta cuota todavía no tiene un pago registrado."))
        return self.env.ref(
            'wk_school_colombo.report_payment_receipt_action'
        ).report_action(self.move_line_id._wk_tirilla_docs())
