# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

CATEGORIES = [
    ('NOM', 'Nómina'),
    ('LIQ', 'Liquidación'),
    ('VAC', 'Vacaciones'),
    ('CES', 'Cesantías'),
    ('PART_CES', 'Cesantías parciales'),
    ('INTE_CES', 'Intereses de cesantías'),
    ('PRI', 'Prima'),
    ('CON', 'Consolidación'),
    ('OTH', 'Otros')
]


class HrPayslipType(models.Model):
    _name = 'hr.payslip.type'
    _description = 'Categoría de Nómina'
    _order = 'name'

    name = fields.Char(string='Nombre')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)
    category = fields.Selection(
        string='Categoría', selection=CATEGORIES, required=True)
    concepts_ids = fields.Many2many(
        comodel_name='hr.concept', string='Conceptos de Nómina',
        relation='hr_payslip_type_hr_concept_rel')
    novelty_types_ids = fields.Many2many(
        comodel_name='hr.novelty.type', string='Categoría de Novedades',
        relation='hr_payslip_type_hr_novelty_type_rel')
    leave_types_ids = fields.Many2many(
        comodel_name='hr.leave.type', string='Categoría de Ausencias',
        relation='hr_payslip_type_hr_leave_type_rel')
    overtime_types_ids = fields.Many2many(
        comodel_name='hr.overtime.type', string='Categoría de Horas Extras',
        relation='hr_payslip_type_hr_overtime_type_rel')

    def get_categories_novelty(self, categories_novelty):
        if self.id in categories_novelty:
            return
        categories_novelty[self.id] = tmp = {}
        if self.novelty_types_ids.ids:
            tmp['hr.novelty.line'] = self.novelty_types_ids.ids
        if self.leave_types_ids.ids:
            tmp['hr.leave.line'] = self.leave_types_ids.ids
        if self.overtime_types_ids.ids:
            tmp['hr.overtime'] = self.overtime_types_ids.ids

    def get_sorted_concepts(self, sorted_concepts):
        if self.id in sorted_concepts:
            return
        sorted_concepts[self.id] = sorted(
            self.concepts_ids, key=lambda x: x.get_seq_concept_category())
