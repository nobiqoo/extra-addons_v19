# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

CATEGORY_TYPE = [
    ('SICKNESS', 'Incapacidad de enfermedad general'),
    ('MAT_LIC', 'Licencia de maternidad'),
    ('PAT_LIC', 'Licencia de paternidad'),
    ('AT_EP', 'Accidente de trabajo - Enfermedad profesional'),
    ('NO_PAY', 'Sin paga'),
    ('PAY', 'Con Paga'),
    ('VAC', 'Vacaciones'),
    ('VAC_MONEY', 'Vacaciones en dinero')
]

HELP_MESSAGE = 'Permite que el valor del día sea menor a un día de SMMLV'

class HrLeaveType(models.Model):
    _name = 'hr.leave.type'
    _inherit = 'model.basic.payslip.novelty.type'
    _description = 'Categoría de Ausencias'
    _order = 'name'

    category_type = fields.Selection(
        string='Tipo', selection=CATEGORY_TYPE, required=True)

    b2 = fields.Float(string='De 1 a 2 días')
    b90 = fields.Float(string='De 3 a 90 días')
    b180 = fields.Float(string='De 91 a 180 días')
    a180 = fields.Float(string='De 181 días en adelante')

    apply_day_31 = fields.Boolean(string='Aplica día 31')
    discount_rest_day = fields.Boolean(string='Descontar día de descanso')

    no_smmlv_limit_b2 = fields.Boolean(
        'Aceptar menor a SMMLV De 1 a 2 días', help=HELP_MESSAGE, default=False)
    no_smmlv_limit_b90 = fields.Boolean(
        'Aceptar menor a SMMLV De 3 a 90 días', help=HELP_MESSAGE, default=False)
    no_smmlv_limit_b180 = fields.Boolean(
        'Aceptar menor a SMMLV De 91 a 180 días', help=HELP_MESSAGE, default=False)
    no_smmlv_limit_a180 = fields.Boolean(
        'Aceptar menor a SMMLV De 181 días en adelante', help=HELP_MESSAGE, default=False)

    # VAC Payment Strategy
    holiday_payment_strategy = fields.Selection([
        ('with_avg', 'Promedio salarial último año'),
        ('with_wage', 'Salario actual'),
        ('with_mixed', 'Promedio en días de vacaciones'),
        ('with_all_avg', 'Promedio total')
    ], string='Método de pago')

    is_holiday_leave = fields.Boolean(
        string='Vacaciones días no habiles')


    def get_rate_concept_id(self, sequence):
        concept = self.env['hr.concept']
        if self.category_type == 'AT_EP':
            rate = 100
            no_smmlv_limit = 0
            code = 'ATEP' if sequence <= 1 else 'ATEP_P2'
            concept_id = concept.search([('code', '=', code)], limit=1).id or None
        elif self.category_type != 'SICKNESS':
            rate = 100
            concept_id = None
            no_smmlv_limit = 0
        elif 1 <= sequence <= 2:
            rate = self.b2
            concept_id = concept.search([('code', '=', 'EG_B2')], limit=1).id
            no_smmlv_limit = self.no_smmlv_limit_b2
        elif 3 <= sequence <= 90:
            rate = self.b90
            concept_id = concept.search([('code', '=', 'EG_B90')], limit=1).id
            no_smmlv_limit = self.no_smmlv_limit_b90
        elif 91 <= sequence <= 180:
            rate = self.b180
            concept_id = concept.search([('code', '=', 'EG_B180')], limit=1).id
            no_smmlv_limit = self.no_smmlv_limit_b180
        elif 181 <= sequence:
            rate = self.a180
            concept_id = concept.search([('code', '=', 'EG_A180')], limit=1).id
            no_smmlv_limit = self.no_smmlv_limit_a180
        else:
            rate = 0
            concept_id = None
            no_smmlv_limit = 0
        return rate, concept_id or None, no_smmlv_limit
