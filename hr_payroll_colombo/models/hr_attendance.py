# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

APPROVAL_GROUPS = (
    'hr_attendance.group_hr_attendance_manager',
    'hr.group_hr_manager',
)

# Campos que no se pueden cambiar mientras la asistencia esté aprobada: sus
# horas ya están sumadas en la novedad del mes.
LOCKED_FIELDS = {'school_class_id', 'payroll_hours', 'employee_id',
                 'check_in', 'check_out'}


def _month_end(date_ref):
    return date_ref.replace(day=1) + relativedelta(months=1, days=-1)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    school_class_id = fields.Many2one(
        comodel_name='wk.school.class',
        string='Curso',
        help='Clase ofertada que el profesor dictó en este registro.')
    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Cuenta Analítica',
        related='school_class_id.analytic_account_id',
        store=True, readonly=True)
    payroll_hours = fields.Float(
        string='Horas para Nómina',
        compute='_compute_payroll_hours', store=True, readonly=False,
        help='Horas que se llevan a la novedad de nómina. Se propone el '
             'tiempo trabajado del registro y puede ajustarse.')
    approved_for_payroll = fields.Boolean(
        string='Aprobado para Nómina', copy=False,
        help='Solo las asistencias aprobadas se consolidan en la novedad de '
             'horas del profesor.')
    payroll_novelty_line_id = fields.Many2one(
        comodel_name='hr.novelty.teacher.hour',
        string='Línea de Novedad',
        copy=False, readonly=True, ondelete='set null',
        help='Línea de la novedad en la que se consolidaron estas horas.')
    payroll_novelty_id = fields.Many2one(
        comodel_name='hr.novelty',
        string='Novedad de Nómina',
        related='payroll_novelty_line_id.novelty_id',
        store=True, readonly=True)
    payroll_novelty_state = fields.Selection(
        related='payroll_novelty_id.state', string='Estado de la Novedad')
    can_approve_payroll = fields.Boolean(
        compute='_compute_can_approve_payroll')

    @api.depends('worked_hours')
    def _compute_payroll_hours(self):
        for record in self:
            record.payroll_hours = record.worked_hours

    def _compute_can_approve_payroll(self):
        can_approve = any(self.env.user.has_group(group)
                          for group in APPROVAL_GROUPS)
        for record in self:
            record.can_approve_payroll = can_approve

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('approved_for_payroll') for vals in vals_list):
            self._check_payroll_approval_rights()
        records = super().create(vals_list)
        records.filtered('approved_for_payroll')._consolidate_payroll_hours()
        return records

    def write(self, vals):
        if 'approved_for_payroll' in vals:
            self._check_payroll_approval_rights()
        if LOCKED_FIELDS & set(vals):
            approved = self.filtered('approved_for_payroll')
            if approved and vals.get('approved_for_payroll', True):
                raise ValidationError(
                    'Desapruebe para nómina la asistencia de '
                    f'{approved[0].employee_id.name} antes de cambiar el curso, '
                    'las horas o las fechas: sus horas ya están sumadas en la '
                    'novedad del mes.')
        if 'approved_for_payroll' in vals and not vals['approved_for_payroll']:
            self.filtered('payroll_novelty_line_id')._release_payroll_hours()
        res = super().write(vals)
        if vals.get('approved_for_payroll'):
            self.filtered(lambda a: a.approved_for_payroll
                          and not a.payroll_novelty_line_id
                          )._consolidate_payroll_hours()
        return res

    def unlink(self):
        self.filtered('payroll_novelty_line_id')._release_payroll_hours()
        return super().unlink()

    # ------------------------------------------------------------------
    # Consolidación de horas en la novedad del mes
    # ------------------------------------------------------------------
    @api.model
    def _get_teacher_contract(self, employee):
        contract = self.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
        ], limit=1)
        if not contract:
            raise ValidationError(
                f'{employee.name} no tiene un contrato vigente.')
        if not contract.has_teacher_fraction():
            raise ValidationError(
                f'El contrato de {employee.name} no está marcado como '
                'Profesor en la pestaña Tipo de Empleado.')
        return contract

    def _consolidate_payroll_hours(self, novelty_type=None):
        """Suma las horas de las asistencias aprobadas a la novedad en
        borrador del profesor para el mes de la asistencia, con una línea
        por curso. Si el mes aún no tiene novedad en borrador, la crea.

        Devuelve las novedades afectadas.
        """
        Novelty = self.env['hr.novelty'].sudo()
        Line = self.env['hr.novelty.teacher.hour'].sudo()
        novelties = Novelty
        if not self:
            return novelties
        novelty_type = novelty_type or self.env['hr.novelty.type'].sudo(
            ).search([('is_teacher_hours', '=', True)], limit=1)
        if not novelty_type:
            raise ValidationError(
                'No hay una categoría de novedad marcada como Horas de '
                'profesor.')
        groups = self.grouped(lambda a: (a.employee_id, _month_end(a.date)))
        for (employee, month_end), attendances in groups.items():
            contract = self._get_teacher_contract(employee)
            hour_value = contract.get_hour_value(month_end)
            if not hour_value:
                raise ValidationError(
                    f'El contrato de {employee.name} no tiene valor hora '
                    'vigente en el <Histórico de Valor Hora>.')
            novelty = Novelty.search([
                ('contract_id', '=', contract.id),
                ('novelty_type_id', '=', novelty_type.id),
                ('state', '=', 'draft'),
                ('date_start', '=', month_end),
            ], limit=1)
            if not novelty:
                novelty = Novelty.with_company(contract.company_id).create({
                    'contract_id': contract.id,
                    'employee_id': employee.id,
                    'novelty_type_id': novelty_type.id,
                    'company_id': contract.company_id.id,
                    'date_start': month_end,
                    'type_novelty': 'STATIC',
                })
            for school_class, class_attendances in attendances.grouped(
                    'school_class_id').items():
                line = novelty.teacher_hour_line_ids.filtered(
                    lambda l: l.school_class_id == school_class)[:1]
                if not line:
                    line = Line.create({
                        'novelty_id': novelty.id,
                        'school_class_id': school_class.id,
                        'analytic_account_id':
                            school_class.analytic_account_id.id,
                        'hours': 0.0,
                        'hour_value': hour_value,
                    })
                class_attendances.sudo().write(
                    {'payroll_novelty_line_id': line.id})
                line._sync_hours()
            novelties |= novelty
        return novelties

    def _release_payroll_hours(self):
        """Saca las horas de la novedad del mes. Solo se puede mientras la
        novedad esté en borrador; las líneas y la novedad que queden sin
        horas se eliminan."""
        lines = self.sudo().mapped('payroll_novelty_line_id')
        locked = lines.mapped('novelty_id').filtered(
            lambda n: n.state != 'draft')
        if locked:
            raise ValidationError(
                f'La novedad {locked[0].name} ya está confirmada: no se pueden '
                'quitar sus horas. Devuélvala a borrador primero.')
        novelties = lines.mapped('novelty_id')
        self.sudo().write({'payroll_novelty_line_id': False})
        for line in lines:
            if line.attendance_ids:
                line._sync_hours()
            else:
                line.unlink()
        novelties.filtered(lambda n: not n.teacher_hour_line_ids).unlink()

    @api.model
    def _check_payroll_approval_rights(self):
        if not any(self.env.user.has_group(group) for group in APPROVAL_GROUPS):
            raise ValidationError(
                'Solo el Gerente de Asistencias o el Administrador de Recursos '
                'Humanos pueden aprobar horas para nómina.')

    @api.constrains('approved_for_payroll', 'school_class_id', 'payroll_hours')
    def _check_approved_attendance(self):
        for record in self.filtered('approved_for_payroll'):
            if not record.school_class_id:
                raise ValidationError(
                    'Indique el curso antes de aprobar para nómina la '
                    f'asistencia de {record.employee_id.name}.')
            if record.payroll_hours <= 0:
                raise ValidationError(
                    'Las horas para nómina deben ser mayores a cero en la '
                    f'asistencia de {record.employee_id.name}.')
            if not record.analytic_account_id:
                raise ValidationError(
                    'El curso '
                    f'{record.school_class_id.display_name} no tiene cuenta '
                    'analítica configurada.')

    def action_approve_for_payroll(self):
        self._check_payroll_approval_rights()
        self.write({'approved_for_payroll': True})

    def action_refuse_for_payroll(self):
        self._check_payroll_approval_rights()
        self.write({'approved_for_payroll': False})
