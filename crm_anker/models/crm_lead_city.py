# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo.exceptions import ValidationError


class CrmLeadCity(models.Model):
    _name = 'crm.lead.city'
    _description = 'Ciudad CRM'

    name = fields.Char(
        string='Nombre',
        required=True
    )
    country_id = fields.Many2one(
        comodel_name='crm.lead.country',
        string='País',
        required=True
    )
