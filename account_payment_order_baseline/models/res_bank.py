# -*- coding: utf-8 -*-

from odoo import _, api, models


class ResBank(models.Model):
    _inherit = "res.bank"

    @api.constrains("bic")
    def check_bic_length(self):
        return True
