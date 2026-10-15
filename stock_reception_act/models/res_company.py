# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    reception_act_code = fields.Char(
        string='Reception Act Format Code',
    )
    reception_act_version = fields.Char(
        string='Reception Act Format Version',
    )
    reception_act_date = fields.Date(
        string='Reception Act Format Effective Date',
    )
