# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    api_integration_journal_id = fields.Many2one(
        related='company_id.api_integration_journal_id',
        string='Diario para Integración API',
        readonly=False,
    )

    api_rest_api_key = fields.Char(
        related='company_id.api_rest_api_key',
        string='API Key de Integración',
        readonly=False,
    )
