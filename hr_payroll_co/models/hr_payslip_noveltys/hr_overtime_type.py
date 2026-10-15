# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class HrOvertimeType(models.Model):
    _name = 'hr.overtime.type'
    _inherit = 'model.basic.payslip.novelty.type'
    _description = 'Categoría de Horas Extras'
    _order = 'name'

    rate = fields.Float(string='Factor')
