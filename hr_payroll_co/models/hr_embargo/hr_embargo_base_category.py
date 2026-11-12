# -*- coding: utf-8 -*-
from odoo import models, fields

# Restricted on purpose to the hr.concept/hr.payslip.line categories (see
# CATEGORY_PAYSLIP in model_basic_payslip_novelty_type.py) that make sense as a
# garnishment base: earnings-like buckets only. Deliberately excludes
# non_taxed_earnings, deductions, contributions, provisions and subtotals (e.g.
# 'subtotals' would let someone pick NETO itself, double-counting the base). A
# free-text code here would silently contribute 0 to the base on any typo/mismatch
# with the real technical code, with no error — a Selection removes that risk.
BASE_CATEGORY_CODE = [
    ('earnings', 'DEVENGADO'),
    ('o_salarial_earnings', 'OTROS DEVENGOS SALARIALES'),
    ('comp_earnings', 'INGRESOS COMPLEMENTARIOS'),
    ('o_rights', 'OTROS DERECHOS'),
    ('o_earnings', 'OTROS DEVENGOS'),
]


class HrEmbargoBaseCategory(models.Model):
    _name = 'hr.embargo.base.category'
    _description = 'Garnishment Base Category'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Selection(
        string='Technical Code', selection=BASE_CATEGORY_CODE, required=True,
        help='Technical payslip category this entry maps to.')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', default=lambda self: self.env.company)

    _code_company_id_uniq = models.Constraint(
        'UNIQUE (code, company_id)',
        'The technical code must be unique per company.',
    )
