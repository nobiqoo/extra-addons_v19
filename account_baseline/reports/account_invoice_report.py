# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools import SQL


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    city = fields.Char(string='City')

    @api.model
    def _select(self):
        return SQL(
            """
            %s,
            partner.city as city
            """,
            super()._select()
        )
