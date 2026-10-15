# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

EMPLOYEE_CATEGORY = [
    ('administrative', 'Administrativo'),
    ('teacher', 'Profesor'),
]

TEACHER_SUBTYPE = [
    ('type_10', 'Tipo 10'),
    ('type_12', 'Tipo 12'),
    ('mixed', 'Mixto'),
]

# Subtipos que liquidan prestaciones sobre la base especial de 330 días,
# según lo marcado en Ajustes.
SPECIAL_SUBTYPE_PARAM = {
    'type_10': 'hr_payroll_colombo.benefits_330_type_10',
    'type_12': 'hr_payroll_colombo.benefits_330_type_12',
    'mixed': 'hr_payroll_colombo.benefits_330_mixed',
}

STANDARD_DAYS_BASE = 360
SPECIAL_DAYS_BASE = 330


class HrContract(models.Model):
    _inherit = 'hr.contract'

    employee_category = fields.Selection(
        selection=EMPLOYEE_CATEGORY, string='Categoría de Empleado',
        help='Determina el comportamiento del contrato en el motor de nómina.')
    teacher_subtype = fields.Selection(
        selection=TEACHER_SUBTYPE, string='Subtipo de Profesor',
        help='Tipo 12 liquida prestaciones sobre 360 días, Tipo 10 sobre 330 '
             'y Mixto combina el salario básico con el valor de las horas.')
    special_benefits_calculation = fields.Boolean(
        string='Cálculo Especial de Prestaciones',
        compute='_compute_special_benefits_calculation',
        help='Se marca solo cuando la política de cálculo está activa y el '
             'subtipo tiene marcado en Ajustes el cálculo de prestaciones '
             'sobre 330 días (por defecto Tipo 10 y Mixto). Indica al motor '
             'de nómina que cesantías, intereses, prima y vacaciones se '
             'liquidan sobre 330 días en lugar de 360.')
    benefits_days_base = fields.Integer(
        string='Base Días Prestaciones',
        compute='_compute_special_benefits_calculation',
        help='Días del año sobre los que se causan las prestaciones del '
             'contrato. En el contrato mixto aplica a todo el contrato, '
             'salario básico y horas.')
    hour_value_history_ids = fields.One2many(
        comodel_name='hour.value.update.history', inverse_name='contract_id',
        string='Histórico de Valor Hora')
    teacher_hour_line_ids = fields.One2many(
        comodel_name='hr.novelty.teacher.hour', inverse_name='contract_id',
        string='Histórico de horas', readonly=True,
        groups='hr_payroll_co.user_payslip,hr_payroll_co.manager_payslip,'
               'hr_attendance.group_hr_attendance_manager',
        help='Horas aprobadas para nómina, consolidadas por curso y mes, con '
             'su estado de pago.')
    hour_value = fields.Float(
        string='Valor Hora Vigente',
        compute='_compute_hour_value',
        help='Último valor hora registrado en el histórico.')

    @api.depends('employee_category', 'teacher_subtype')
    def _compute_special_benefits_calculation(self):
        for record in self:
            is_special = record.has_special_benefits_calculation()
            record.special_benefits_calculation = is_special
            record.benefits_days_base = (
                SPECIAL_DAYS_BASE if is_special else STANDARD_DAYS_BASE)

    def has_special_benefits_calculation(self):
        """El contrato liquida prestaciones sobre 330 días: la política de
        cálculo está activa y su subtipo está marcado en Ajustes."""
        self.ensure_one()
        subtype_param = SPECIAL_SUBTYPE_PARAM.get(self.teacher_subtype)
        if not (self.is_teacher() and subtype_param):
            return False
        config = self.env['ir.config_parameter'].sudo()
        return bool(
            config.get_param('hr_payroll_colombo.apply_contract_type_policy')
            and config.get_param(subtype_param))

    def get_benefits_days_base(self):
        if self.has_special_benefits_calculation():
            return SPECIAL_DAYS_BASE
        return super().get_benefits_days_base()

    # El profesor Tipo 10 o Tipo 12 guarda en el salario el valor hora, que no
    # es un sueldo mensual. Mientras se liquidan sus prestaciones el contrato
    # se lee con el contexto teacher_hours_wage y su salario cuenta como cero,
    # así la base sale solo del promedio de las horas devengadas.
    def get_wage(self, date_end, date_start=False):
        res = super().get_wage(date_end, date_start)
        if self.env.context.get('teacher_hours_wage'):
            res = dict(res, wage=0)
            if 'last_wage' in res:
                res['last_wage'] = 0
        return res

    def has_change_salary(self, date_from, date_to):
        if self.env.context.get('teacher_hours_wage'):
            return False
        return super().has_change_salary(date_from, date_to)

    def average_wage_history_by_days(self, date_from, date_to, excludes=[],
                                     date_excludes=[]):
        if self.env.context.get('teacher_hours_wage'):
            return {}
        return super().average_wage_history_by_days(
            date_from, date_to, excludes, date_excludes)

    @api.depends('hour_value_history_ids.hour_value',
                 'hour_value_history_ids.date')
    def _compute_hour_value(self):
        for record in self:
            record.hour_value = record.get_hour_value(fields.Date.today())

    @api.onchange('employee_category')
    def _onchange_employee_category(self):
        if self.employee_category != 'teacher':
            self.teacher_subtype = False

    @api.constrains('employee_category', 'teacher_subtype')
    def _check_teacher_subtype(self):
        for record in self:
            if record.employee_category != 'teacher' and record.teacher_subtype:
                raise ValidationError(
                    'El subtipo de profesor solo aplica a los contratos de '
                    'categoría Profesor.')

    def get_hour_value(self, date_ref):
        """Valor hora vigente en una fecha.

        Toma el registro del histórico con la fecha de inicio más reciente
        que no supere la fecha de referencia.
        """
        self.ensure_one()
        if not date_ref:
            return 0.0
        history = self.hour_value_history_ids.filtered(
            lambda h: h.date <= date_ref).sorted('date')
        return history[-1].hour_value if history else 0.0

    def is_teacher(self):
        self.ensure_one()
        return self.employee_category == 'teacher'

    def is_mixed_teacher(self):
        self.ensure_one()
        return self.is_teacher() and self.teacher_subtype == 'mixed'

    def has_teacher_fraction(self):
        """El contrato liquida una fracción sobre el valor de las horas."""
        self.ensure_one()
        return self.is_teacher()

    def has_administrative_fraction(self):
        """El contrato liquida una fracción sobre el salario básico."""
        self.ensure_one()
        return not self.is_teacher() or self.is_mixed_teacher()

    def check_contract_type_policy(self):
        """Valida los campos que exige la política de cálculo por tipo de
        contrato. Se invoca al liquidar, no al guardar el contrato, para no
        bloquear los contratos ya existentes."""
        self.ensure_one()
        if not self.env['ir.config_parameter'].sudo().get_param(
                'hr_payroll_colombo.apply_contract_type_policy'):
            return
        if not self.employee_category:
            raise ValidationError(
                'Defina la <Categoría de Empleado> en la pestaña Tipo de '
                f'Empleado del contrato de {self.employee_id.name}.')
        if self.employee_category != 'teacher':
            return
        if not self.teacher_subtype:
            raise ValidationError(
                'Defina el <Subtipo de Profesor> en la pestaña Tipo de '
                f'Empleado del contrato de {self.employee_id.name}.')
        if not self.hour_value_history_ids:
            raise ValidationError(
                'Registre el valor hora en el <Histórico de Valor Hora> del '
                f'contrato de {self.employee_id.name}.')
