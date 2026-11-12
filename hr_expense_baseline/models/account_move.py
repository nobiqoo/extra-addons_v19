# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    expense_id = fields.Many2one('hr.expense', string='Expense')

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        # l10n_co_bloodo: las facturas de gastos en diarios de FE se envían después (documento soporte)
        if 'fe_send_later' in self._fields:
            moves.filtered(
                lambda m: m.expense_id and m.journal_id.is_einvoicing and not m.fe_send_later
            ).fe_send_later = True
        return moves

    def _get_voucher_partner(self):
        res = super(AccountMove, self)._get_voucher_partner()
        if self.expense_id:
            res = self.expense_id.employee_id._get_expense_partner()
        return res

    # def _post(self, soft=True):
    #     partner_ids = {}
    #     for move in self:
    #         partner_ids[move.id] = {
    #             line.id: line.partner_id.id for line in move.line_ids
    #         }

    #     res = super(AccountMove, self)._post(soft)

    #     for move in self:
    #         for line in move.line_ids:
    #             if move.id in partner_ids and line.id in partner_ids[move.id]:
    #                 line.partner_id = partner_ids[move.id][line.id]

    #     return res
