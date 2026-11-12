# -*- coding: utf-8 -*-
"""Pago anticipado de cuotas (tarea 11856, requerimiento 2.6) y
Observaciones de la tirilla de pago (tarea 12458).

Cuando "Registrar abono" se invoca sobre UNA sola cuota (ver
wk.fee.installment.line.action_registrar_abono) y el usuario paga mas de lo
que esa cuota debe, el wizard estandar de Odoo concilia la linea apuntada y
deja el sobrante como un saldo abierto en la propia linea del pago. Aqui se
reconcilia ese sobrante, en orden de vencimiento, contra las siguientes cuotas
NO conciliadas de la MISMA factura -sin crear lineas nuevas ni recalcular
fechas/valores programados, tal como exige el requerimiento-.

Con guarda de alcance: solo corre quizo cuando la factura pertenece a un
acuerdo de pago por cuotas (wk.fee.installment.plan); para cualquier otra
factura el comportamiento de Odoo no cambia.
Incidencia PT11849 (2): "Registrar abono" (wk.fee.installment.line.
action_registrar_abono) llama a account.move.line.action_register_payment(),
que abre este wizard estándar (account.payment.register) -NO el wizard
"account.voucher.wizard" que usa el botón "Pagar" de la factura-. El módulo
account_payment_authorization_reconcile solo agregó el campo Authorization
Number a account.voucher.wizard/account.payment, dejando este wizard sin
forma de capturarlo: el abono se podía "crear" igual, y recién fallaba al
validarse (account.payment.action_post -> _check_authorization_number_
required), con un mensaje que no señala dónde corregir. Se replica aquí el
mismo campo/condición para que el abono exija el dato ANTES de crear el
pago, igual que ya ocurre al registrar el pago desde la factura.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    observaciones = fields.Text(string='Observaciones')
    authorization_number = fields.Char(string='Authorization Number')
    authorization_number_required = fields.Boolean(
        compute='_compute_authorization_number_required',
        help="Técnico: obliga el campo Authorization Number en el wizard.")

    @api.depends('payment_type', 'journal_id')
    def _compute_authorization_number_required(self):
        for wizard in self:
            wizard.authorization_number_required = (
                wizard.payment_type == 'inbound' and wizard.journal_id.type != 'cash')

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        payment_vals['observaciones'] = self.observaciones
        payment_vals['authorization_number'] = self.authorization_number
        return payment_vals

    def action_create_payments(self):
        if self.authorization_number_required and not self.authorization_number:
            raise UserError(_(
                "Please set the Authorization Number before registering this payment."))
        return super().action_create_payments()

    def _reconcile_payments(self, to_process, edit_mode=False):
        super()._reconcile_payments(to_process, edit_mode=edit_mode)

        valid_account_types = self.env['account.payment']._get_valid_payment_account_types()
        domain = [
            ('parent_state', '=', 'posted'),
            ('account_type', 'in', valid_account_types),
            ('reconciled', '=', False),
        ]

        for vals in to_process:
            targeted = vals.get('to_reconcile')
            payment = vals.get('payment')
            if not targeted or not payment:
                continue

            invoices = targeted.move_id
            installment_invoices = invoices.filtered(lambda m: m.installment_plan_id)
            if not installment_invoices:
                continue

            for invoice in installment_invoices:
                next_lines = invoice.line_ids.filtered(
                    lambda l: l.display_type == 'payment_term'
                    and not l.reconciled
                    and l.id not in targeted.ids
                ).sorted('date_maturity')

                for next_line in next_lines:
                    payment_lines = payment.move_id.line_ids.filtered_domain(domain)
                    if not payment_lines:
                        break
                    for account in payment_lines.account_id:
                        (payment_lines + next_line).filtered_domain(
                            [('account_id', '=', account.id), ('reconciled', '=', False)]
                        ).reconcile()
