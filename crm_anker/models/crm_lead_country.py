# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo.exceptions import ValidationError


class CrmLeadCountry(models.Model):
    _name = 'crm.lead.country'
    _description = 'País CRM'

    name = fields.Char(
        string='Nombre',
        required=True
    )
