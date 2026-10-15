# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipLineLog(models.Model):
    _inherit = 'hr.payslip.line.log'

    days_base = fields.Integer(
        string='Base Días',
        help='Base de días de liquidación con la que se calculó la provisión '
             'de la fracción de profesor: 330 en Tipo 10 y Mixto, 360 en '
             'Tipo 12.')
