# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    reception_act_code = fields.Char(
        related='company_id.reception_act_code',
        readonly=False,
    )
    reception_act_version = fields.Char(
        related='company_id.reception_act_version',
        readonly=False,
    )
    reception_act_date = fields.Date(
        related='company_id.reception_act_date',
        readonly=False,
    )
