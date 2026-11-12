# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    payment_last_date = fields.Date(
        string='Fecha último pago',
        compute='_compute_portal_payment_info',
    )
    payment_paid_amount = fields.Monetary(
        string='Valor del pago',
        currency_field='currency_id',
        compute='_compute_portal_payment_info',
    )

    @api.depends('amount_total', 'amount_residual', 'invoice_payments_widget', 'payment_state')
    def _compute_portal_payment_info(self):
        """Fecha del último pago y valor pagado, para la lista de facturas del portal.

        Se lee con sudo porque el usuario de portal no tiene acceso a los pagos.
        Sin pagos, ambos campos quedan vacíos.
        """
        for move in self:
            last_date = False
            paid_amount = 0.0
            if move.state == 'posted':
                move_sudo = move.sudo()
                widget = move_sudo.invoice_payments_widget or {}
                dates = [
                    fields.Date.to_date(item['date'])
                    for item in (widget.get('content') or [])
                    if item.get('date')
                ]
                if dates:
                    last_date = max(dates)
                    paid_amount = move_sudo.amount_total - move_sudo.amount_residual
            move.payment_last_date = last_date
            move.payment_paid_amount = paid_amount
