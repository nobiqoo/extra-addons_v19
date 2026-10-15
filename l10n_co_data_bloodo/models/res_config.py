# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    activate_duplicate_contacts = fields.Boolean(
        string='Activate Duplicate Contacts',
        related='company_id.duplicate_contacts',
        readonly=False)
