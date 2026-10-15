# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class AccountMove(models.Model):
    _inherit = 'account.move'

    voucher_id = fields.Many2one(
        comodel_name='account.voucher',
        ondelete='cascade',
        readonly=True,
        copy=False
    )

    def action_register_payment(self):
        return {
            'name': _('Register Voucher'),
            'res_model': 'account.voucher.wizard',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move',
                'active_ids': self.ids,
                'default_active_bool': len(self.ids) > 1,
                'default_amount': self and self[0].amount_residual or False,
                'default_currency_id': self and self[0].currency_id.id or False,
                'default_voucher_reference': self and self[0].name or False,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def action_post(self):
        for record in self:
            # POLITICA: VALIDACIÓN DIARIO EN COMPAÑIA PARA ANTICIPOS
            if record.company_id.active_payment_advance:
                if not self.env.company.journal_id:
                    raise ValidationError(
                        _('Debe elegir un diario para el cruce de cuentas desde ajustes generales'))

        res = super(AccountMove, self).action_post()
        for record in self:
            if record.company_id.active_payment_advance:
                Voucher = self.env['account.voucher']
                Order = self.env['sale.order']
                if record.move_type == 'out_invoice':
                    order = Order.search(
                        [('name', '=', record.invoice_origin)]
                    )
                    if order:
                        accounts_advance = order.account_voucher_ids
                        invoices = order.invoice_ids
                        invoices_post = []
                        # Inicia la creación de cruce por anticipos si
                        # se existen anticipos en la orden
                        if accounts_advance:
                            # for invoice in invoices:
                            #    invoice.action_post()
                            #    invoices_post.append(invoice)

                            vals = {
                                'voucher_date': datetime.today(),
                                'date': datetime.today(),
                                'partner_id': order.partner_id.id,
                                'voucher_type': 'cross',
                                'writeoff_option': 'with_writeoff',
                                # 'writeoff_option': 'without_writeoff',
                                'journal_id': self.env.company.journal_id.id
                            }

                            account_voucher = Voucher.create(vals)
                            # Prepare account_id
                            account_voucher._onchange_partner_id()

                            # Llenar lineas por cobrar y pagar
                            line_ids = order.account_voucher_ids.move_id.line_ids
                            line_ids += self.line_ids
                            account_voucher = account_voucher.with_context(
                                line_ids=line_ids.ids
                            )
                            account_voucher.compute_line_ids()

                            for line in account_voucher.line_passive_ids:
                                line.amount = line.amount_unreconciled

                            for line in account_voucher.line_active_ids:
                                line.amount = line.amount_unreconciled

                            if account_voucher.writeoff_amount != 0.00:
                                reconcile_account = account_voucher.company_id.voucher_account_id or account_voucher.account_id
                                reconcile_vals = {
                                    'account_id': reconcile_account.id,
                                    'comment': order.name,
                                    'amount': account_voucher.writeoff_amount
                                }
                                account_voucher.write(
                                    {'line_reconcile_ids': [(0, 0, reconcile_vals)]}
                                )

                            account_voucher.confirm_action_post = True

                            account_voucher.action_post()
        return res

    def _get_unbalanced_moves(self, container):
        if self._context.get('check_move_validity', 'not_set') == False:
            return
        return super()._get_unbalanced_moves(container)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    voucher_line_id = fields.Many2one(
        comodel_name='account.move.line',
        string='Voucher Line'
    )
