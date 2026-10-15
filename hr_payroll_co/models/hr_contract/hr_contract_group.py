# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HRContractGroup(models.Model):
    _name = 'hr.contract.group'
    _description = 'Grupo de Contratos'

    name = fields.Char(string='Nombre de Grupo')
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)
