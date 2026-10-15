# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountAsset(models.Model):
    _inherit = "account.asset"

    iva_value = fields.Monetary(string='Valor IVA', currency_field='currency_id')
