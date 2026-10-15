# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    petty_cash_manager = fields.Boolean()

    petty_cash_journal = fields.Many2one(
        "account.journal", domain=[("petty_cash", "=", True)]
    )

    petty_cash_opened = fields.Boolean(default=False)

    @api.onchange('petty_cash_manager')
    def _onchange_petty_cash_manager(self):
        available_journals = self.env['account.journal'].search(
            [('petty_cash', '=', True), ('is_assigned', '=', False)])
        return {'domain': {'petty_cash_journal': [('id', 'in', available_journals.ids)]}}
