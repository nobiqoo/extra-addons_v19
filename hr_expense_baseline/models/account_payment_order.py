# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountPaymentOrder(models.Model):
    _inherit = 'account.payment.order'

    def generated2uploaded(self):
        res = super().generated2uploaded()
        self._apo_postprocess_from_order()
        return res

    def _apo_find_payments(self):
        payments = self.env['account.payment']
        for o in self:
            if hasattr(o, 'payment_ids') and o.payment_ids:
                payments |= o.payment_ids
                continue
            if hasattr(o, 'line_ids') and o.line_ids:
                if hasattr(o.line_ids, 'payment_id'):
                    payments |= o.line_ids.mapped('payment_id')
                elif hasattr(o.line_ids, 'payment_ids'):
                    payments |= o.line_ids.mapped('payment_ids')
        return payments

    def _apo_find_invoices_from_payments(self, payments):
        invoices = self.env['account.move']
        if not payments:
            return invoices
        if hasattr(payments, 'reconciled_invoice_ids'):
            invoices |= payments.mapped('reconciled_invoice_ids')
        if not invoices:
            for pay in payments:
                move = getattr(pay, 'move_id', False)
                if not move:
                    continue
                lines = move.line_ids
                counterpart_ml = (
                    lines.mapped('matched_debit_ids.credit_move_id')
                    | lines.mapped('matched_credit_ids.debit_move_id')
                )
                inv_moves = counterpart_ml.mapped('move_id').filtered(
                    lambda m: m.move_type in ('in_invoice', 'in_refund')
                )
                invoices |= inv_moves
        return invoices

    def _apo_find_invoices_from_order_lines(self):
        invoices = self.env['account.move']
        for o in self:
            for attr in ('line_ids', 'payment_line_ids', 'order_line_ids'):
                if not hasattr(o, attr):
                    continue
                lines = getattr(o, attr)
                if not lines:
                    continue
                if hasattr(lines, 'move_line_id'):
                    invoices |= lines.mapped('move_line_id.move_id').filtered(
                        lambda m: m.move_type in ('in_invoice', 'in_refund')
                    )
                if hasattr(lines, 'ml_ids'):
                    invoices |= lines.mapped('ml_ids.move_id').filtered(
                        lambda m: m.move_type in ('in_invoice', 'in_refund')
                    )
        return invoices

    def _apo_collect_invoices(self):
        payments = self._apo_find_payments()
        invoices = self._apo_find_invoices_from_payments(payments)
        if not invoices:
            invoices = self._apo_find_invoices_from_order_lines()
        _logger.info("[APO %s] facturas detectadas: %s",
                     ",".join(self.mapped('name')),
                     ",".join(invoices.mapped('name')))
        return invoices


    def _apo_replenish_petty_cash(self, expenses, invs_for_group):
        company = expenses[:1].company_id
        company_currency = company.currency_id

        amount_company = 0.0
        for inv in invs_for_group:
            amt = inv.amount_total
            cur = inv.currency_id or company_currency
            date = inv.invoice_date or fields.Date.context_today(self)
            if cur != company_currency:
                amt = cur._convert(amt, company_currency, company, date)
            amount_company += amt
        if not amount_company:
            return

        partner = expenses[:1].petty_cash_responsible_id or expenses[:1].employee_id.sudo().work_contact_id
        petty_journal = getattr(partner, 'petty_cash_journal', False)
        if not petty_journal:
            raise UserError(_("No hay diario de Caja Menor asignado al responsable (%s).") % (partner.display_name))

        if hasattr(petty_journal, 'increase_fund'):
            msg = _("Reposición Caja Menor - Orden de pago %s") % ", ".join(self.mapped('name'))
            try:
                petty_journal.increase_fund(amount_company, ref=msg)
                return
            except TypeError:
                petty_journal.increase_fund(amount_company)
                return
            except Exception:
                _logger.exception("[APO] increase_fund() falló; uso asiento manual de reposición.")

        default_liquidity = petty_journal.default_account_id
        refund_acc = getattr(petty_journal, 'account_refund_petty_cash', False) or getattr(company, 'refund_expense_account', False)
        if not default_liquidity or not refund_acc:
            raise UserError(_("Configura la cuenta por defecto del diario y la cuenta de reembolso de Caja Menor."))

        Move = self.env['account.move'].with_company(company)
        move_vals = {
            'move_type': 'entry',
            'date': fields.Date.context_today(self),
            'journal_id': petty_journal.id,
            'ref': _("Reposición Caja Menor - Orden de pago %s") % ", ".join(self.mapped('name')),
            'line_ids': [
                (0, 0, {'account_id': default_liquidity.id, 'debit': amount_company, 'credit': 0.0, 'name': _("Reposición Caja Menor")}),
                (0, 0, {'account_id': refund_acc.id, 'debit': 0.0, 'credit': amount_company, 'name': _("Reposición Caja Menor"), 'partner_id': partner.id}),
            ]
        }
        Move.create(move_vals).action_post()

    def _apo_postprocess_from_order(self):
        invoices = self._apo_collect_invoices()
        if not invoices:
            _logger.info("[APO %s] No se hallaron facturas ligadas a la orden.", ",".join(self.mapped('name')))
            return

        expense_moves = invoices.filtered(lambda m: hasattr(m, 'expense_id') and m.expense_id)
        if not expense_moves:
            _logger.info("[APO %s] No hay facturas con expense_id; nada que reponer/legalizar.", ",".join(self.mapped('name')))
            return

        # En Odoo 19 ya no existe hr.expense.sheet: el tipo de caja menor y su
        # responsable viven directamente en hr.expense.
        petty_expenses = expense_moves.mapped('expense_id').filtered(
            lambda e: e.type == 'expense_petty_cash'
        )
        groups = {}
        for exp in petty_expenses:
            groups.setdefault(exp.petty_cash_responsible_id, self.env['hr.expense'])
            groups[exp.petty_cash_responsible_id] |= exp
        for partner, expenses in groups.items():
            invs_for_group = expense_moves.filtered(lambda m: m.expense_id in expenses)
            try:
                self._apo_replenish_petty_cash(expenses, invs_for_group)
            except Exception as e:
                _logger.exception("[APO] Error reponiendo Caja Menor para %s: %s",
                                  partner.display_name or expenses[:1].name, e)
                expenses[:1]._message_log(body="⚠️ Error reponiendo Caja Menor desde la Orden de Pago. Revise configuración.")

        advances = expense_moves.mapped('expense_id.advance_id')
        for adv in advances:
            if hasattr(adv, 'recompute_legalization_state'):
                adv.recompute_legalization_state()
