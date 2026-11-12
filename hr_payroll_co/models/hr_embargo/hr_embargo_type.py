# -*- coding: utf-8 -*-
from odoo import models, fields, api

LEGAL_TYPE = [
    ('alimony', 'Alimony'),
    ('ordinary', 'Ordinary'),
    ('coercive', 'Coercive'),
    ('cooperative', 'Cooperative'),
    ('judicial', 'Judicial'),
    ('other', 'Other'),
]

CALCULATION_TYPE = [
    ('fixed_quota', 'Fixed installment'),
    ('percentage', 'Percentage of payment'),
    ('fifth_over_minimum_with_deductions',
     'Fifth of the amount exceeding the minimum wage (with legal deductions)'),
    ('fifth_over_minimum_without_deductions',
     'Fifth of the amount exceeding the minimum wage (without legal deductions)'),
]

DEFAULT_PRIORITY_BY_LEGAL_TYPE = {
    'alimony': 1,
    'coercive': 2,
    'judicial': 3,
    'cooperative': 4,
    'ordinary': 5,
    'other': 6,
}

# "Código del concepto" of the judicial deposit, per the Banco Agrario flat-file
# design (used to build the Registro de Datos, field 5, in the Fase 2 file).
FILE_CONCEPT_CODE = [
    ('1', 'Judicial deposits'),
    ('2', 'Coercive entities'),
    ('3', 'Release from custody (Excarcelaciones)'),
    ('4', 'Auctions (Remates)'),
    ('5', 'Social benefits'),
    ('6', 'Alimony installments'),
    ('7', 'Judicial fee (Arancel judicial)'),
]

DEFAULT_FILE_CONCEPT_CODE_BY_LEGAL_TYPE = {
    'alimony': '6',
    'coercive': '2',
}


class HrEmbargoType(models.Model):
    _name = 'hr.embargo.type'
    _description = 'Garnishment Type'
    _order = 'priority, name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    priority = fields.Integer(
        string='Priority', default=6,
        help='Default application order when an employee has several active garnishments '
             '(lower numbers apply first). Can be overridden per contract in Garnishment '
             'Priorities.')
    legal_type = fields.Selection(
        string='Legal Type', selection=LEGAL_TYPE, required=True, default='other')
    calculation_type = fields.Selection(
        string='Calculation Type', selection=CALCULATION_TYPE, required=True,
        default='percentage')
    concept_id = fields.Many2one(
        comodel_name='hr.concept', string='Payroll Concept', required=True,
        help='Payroll concept used for the resulting payslip line and accounting entry of '
             "this garnishment type's installments. Must also be added to the relevant "
             'payslip type(s) (Payroll, Service Bonus...) Concepts list so the engine picks '
             'it up.')
    file_concept_code = fields.Selection(
        string='File Concept Code', selection=FILE_CONCEPT_CODE, default='1',
        help='"Código del concepto" used to build the judicial deposit flat file '
             '(Banco Agrario design), field 5 of the Registro de Datos.')
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', default=lambda self: self.env.company)

    _code_company_id_uniq = models.Constraint(
        'UNIQUE (code, company_id)',
        'The code must be unique per company.',
    )

    @api.onchange('legal_type')
    def _onchange_legal_type(self):
        for record in self:
            record.priority = DEFAULT_PRIORITY_BY_LEGAL_TYPE.get(record.legal_type, 6)
            record.file_concept_code = DEFAULT_FILE_CONCEPT_CODE_BY_LEGAL_TYPE.get(
                record.legal_type, '1')

