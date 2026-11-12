# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    teacher_hour_line_id = fields.Many2one(
        comodel_name='hr.novelty.teacher.hour', string='Horas por Curso',
        index='btree_not_null', ondelete='set null',
        help='Curso de la novedad de horas que paga esta línea. Cada curso '
             'del mes va en su propia línea del desprendible.')
