# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    
    @api.model
    def init(self):
        res = super().init()
        self.env.cr.execute("""
            UPDATE res_company
            SET purchase_budget_controll = TRUE
            WHERE purchase_budget_controll IS DISTINCT FROM TRUE
        """)
        return res