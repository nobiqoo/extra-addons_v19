# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    account_payable_cash = fields.Many2one('account.account')
    account_refund_petty_cash = fields.Many2one('account.account')
    account_refund_expensive = fields.Many2one('account.account')

    petty_cash = fields.Boolean(default=False)
    fund = fields.Float(readonly=True)

    is_assigned = fields.Boolean(compute='_compute_is_assigned', store=True)

    def decrease_fund(self, amount):
        self.ensure_one()
        new_fund = self.fund - amount
        if new_fund < 0:
            raise UserError(
                _("The fund cannot be negative."))
        self.write({'fund': new_fund})

    def increase_fund(self, amount):
        self.ensure_one()
        new_fund = self.fund + amount
        self.write({'fund': new_fund})

    @api.depends('petty_cash')
    def _compute_is_assigned(self):
        for record in self:
            record.is_assigned = bool(self.env['res.partner'].search(
                [('petty_cash_journal', '=', record.id)], limit=1))
