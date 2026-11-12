# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmbargoCourt(models.Model):
    _name = 'hr.embargo.court'
    _description = 'Garnishment Court'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Court Code', required=True)
    judicial_account = fields.Char(string='Judicial Account')
    destination_code = fields.Char(
        string='Destination Code',
        help='SBAN code of the destination office this court deposits to, used to build the '
             'judicial deposit flat file.')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', default=lambda self: self.env.company)

    _code_company_id_uniq = models.Constraint(
        'UNIQUE (code, company_id)',
        'The court code must be unique per company.',
    )
