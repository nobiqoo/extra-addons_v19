# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    purchase_import_tariff = fields.Selection(
        related="company_id.purchase_import_tariff", readonly=False
    )
    purchase_import_tax = fields.Boolean(
        related="company_id.purchase_import_tax", readonly=False
    )
    purchase_import_type = fields.Selection(
        related="company_id.purchase_import_type", readonly=False
    )
