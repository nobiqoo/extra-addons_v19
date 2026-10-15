# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    expense_id = fields.Many2one('hr.expense', string='Expense')

    def _get_voucher_partner(self):
        res = super(AccountMove, self)._get_voucher_partner()
        if self.expense_id:
            res = self.expense_id.employee_id.address_home_id
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
