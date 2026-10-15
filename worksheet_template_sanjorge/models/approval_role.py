# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ApprovalRole(models.Model):
    _name = 'approval.role'
    _description = 'Approval Role'

    name = fields.Char(
        string='Name'
    )
