# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_einvoice_journal_id = fields.Many2one(related='pos_config_id.einvoice_journal_id', readonly=False)
    pos_default_check_invoice = fields.Selection(related='pos_config_id.default_check_invoice', readonly=False)
