# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo.exceptions import ValidationError


class CrmLeadState(models.Model):
    _name = 'crm.lead.state'
    _description = 'Estado CRM'

    name = fields.Char(
        string='Nombre',
        required=True
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )
