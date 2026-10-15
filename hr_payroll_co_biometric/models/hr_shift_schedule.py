# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta, date


SCHEDULE_STATE = [
    ('draft', 'Borrador'),
    ('confirmed', 'Confirmado'),
    ('done', 'Ejecutado'),
    ('cancel', 'Cancelado'),
]


class HrShiftSchedule(models.Model):
    """Programación de turnos: cabecera por período/sede"""
    _name = 'hr.shift.schedule'
    _description = 'Programación de Turnos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, name'

    name = fields.Char(
        string='Referencia',
        required=True,
        default='Nueva Programación',
        tracking=True,
    )
    state = fields.Selection(
        selection=SCHEDULE_STATE,
        string='Estado',
        default='draft',
        tracking=True,
    )

    date_start = fields.Date(string='Fecha Inicio', required=True, tracking=True)
    date_end = fields.Date(string='Fecha Fin', required=True, tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )
    address_id = fields.Many2one(
        'res.partner',
        string='Sede / Lugar de Trabajo',
        domain="[('type', 'in', ['other', False])]",
    )
    department_id = fields.Many2one('hr.department', string='Departamento')
    user_id = fields.Many2one(
        'res.users',
        string='Supervisor',
        default=lambda self: self.env.user,
    )

    line_ids = fields.One2many(
        'hr.shift.schedule.line',
        'schedule_id',
        string='Asignaciones',
    )

    line_count = fields.Integer(
        string='# Asignaciones',
        compute='_compute_line_count',
    )
    attendance_record_count = fields.Integer(
        string='# Registros Asistencia',
        compute='_compute_attendance_record_count',
    )

    notes = fields.Text(string='Observaciones')

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def _compute_attendance_record_count(self):
        AttendanceRecord = self.env['hr.attendance.record']
        for rec in self:
            rec.attendance_record_count = AttendanceRecord.search_count([
                ('schedule_line_id.schedule_id', '=', rec.id),
            ])

    def action_view_attendance_records(self):
        self.ensure_one()
        action = self.env.ref('hr_payroll_co_biometric.action_hr_attendance_record').read()[0]
        action['domain'] = [('schedule_line_id.schedule_id', '=', self.id)]
        action['context'] = {
            'default_schedule_id': self.id,
        }
        return action

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start > rec.date_end:
                raise ValidationError('La fecha de inicio debe ser anterior a la fecha de fin.')

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError('Debe agregar al menos una asignación antes de confirmar.')
            rec.state = 'confirmed'

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        for rec in self:
            # Eliminar novedades y registros de asistencia de todas las líneas
            records = rec.line_ids.mapped('attendance_record_id').filtered(bool)
            if records:
                records.mapped('novelty_ids').unlink()
                records.unlink()
            rec.line_ids.write({
                'attendance_record_id': False,
                'state': 'scheduled',
            })
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generate_lines_wizard(self):
        """Abre wizard para generación masiva de asignaciones."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generación Masiva de Turnos',
            'res_model': 'hr.process.attendance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_action': 'generate',
                'default_schedule_id': self.id,
                'default_date_start': self.date_start,
                'default_date_end': self.date_end,
            },
        }

    def action_process_attendance(self):
        """Abre el procesamiento permitiendo ajustar el rango de fechas."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError('Solo se puede procesar programaciones confirmadas.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Procesar Asistencias',
            'res_model': 'hr.process.attendance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_action': 'process',
                'default_schedule_id': self.id,
                'default_date_start': self.date_start,
                'default_date_end': self.date_end,
            },
        }


class HrShiftScheduleLine(models.Model):
    """Una asignación de turno a un empleado en una fecha específica"""
    _name = 'hr.shift.schedule.line'
    _description = 'Línea de Programación de Turno'
    _inherit = ['mail.thread']
    _order = 'work_date, employee_id'

    @api.depends('employee_id', 'work_date', 'shift_id')
    def _compute_display_name(self):
        for rec in self:
            employee_name = rec.employee_id.name or 'Sin empleado'
            work_date = fields.Date.to_string(rec.work_date) if rec.work_date else 'Sin fecha'
            shift_name = rec.shift_id.display_name if rec.shift_id else 'Sin turno'
            rec.display_name = '%s / %s / %s' % (employee_name, work_date, shift_name)

    schedule_id = fields.Many2one(
        'hr.shift.schedule',
        string='Programación',
        required=True,
        ondelete='cascade',
        index=True,
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        index=True,
    )
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contrato',
        compute='_compute_contract',
        store=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        related='employee_id.department_id',
        store=True,
    )

    shift_id = fields.Many2one(
        'hr.shift',
        string='Turno',
        required=True,
    )
    work_date = fields.Date(string='Fecha', required=True, index=True)

    # Hora calculada de inicio/fin del turno en ese día
    planned_start = fields.Datetime(
        string='Inicio Programado',
        compute='_compute_planned_times',
        store=True,
    )
    planned_end = fields.Datetime(
        string='Fin Programado',
        compute='_compute_planned_times',
        store=True,
    )

    address_id = fields.Many2one(
        'res.partner',
        string='Sede',
        related='schedule_id.address_id',
        store=True,
    )

    is_sunday = fields.Boolean(
        string='Dominical',
        compute='_compute_day_type',
        store=True,
    )
    is_holiday = fields.Boolean(
        string='Festivo',
        compute='_compute_day_type',
        store=True,
    )

    state = fields.Selection([
        ('scheduled', 'Programado'),
        ('processed', 'Procesado'),
        ('novelty', 'Con Novedad'),
        ('absent', 'Ausente'),
    ], string='Estado Asistencia', default='scheduled', tracking=True)

    # Resultado de la asistencia real (link al registro procesado)
    attendance_record_id = fields.Many2one(
        'hr.attendance.record',
        string='Registro de Asistencia',
        readonly=True,
    )

    notes = fields.Text(string='Observaciones')

    @api.depends('employee_id', 'work_date')
    def _compute_contract(self):
        for rec in self:
            if not rec.employee_id or not rec.work_date:
                rec.contract_id = False
                continue
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'open'),
            ], limit=1)
            rec.contract_id = contract

    @api.depends(
        'work_date',
        'shift_id',
        'shift_id.assignment_mode',
        'shift_id.hour_from',
        'shift_id.hour_to',
        'shift_id.crosses_midnight',
        'shift_id.weekday_line_ids',
        'shift_id.weekday_line_ids.weekday',
        'shift_id.weekday_line_ids.hour_from',
        'shift_id.weekday_line_ids.hour_to',
        'shift_id.weekday_line_ids.crosses_midnight',
    )
    def _compute_planned_times(self):
        import pytz
        for rec in self:
            if not rec.work_date or not rec.shift_id:
                rec.planned_start = False
                rec.planned_end = False
                continue

            tz_name = rec.employee_id.company_id.partner_id.tz or 'America/Bogota'
            try:
                user_tz = pytz.timezone(tz_name)
            except Exception:
                user_tz = pytz.timezone('America/Bogota')

            shift = rec.shift_id
            weekday_line = shift.get_weekday_line(rec.work_date)
            if shift.assignment_mode == 'weekdays' and not weekday_line:
                rec.planned_start = False
                rec.planned_end = False
                continue

            hour_from = weekday_line.hour_from if weekday_line else shift.hour_from
            hour_to = weekday_line.hour_to if weekday_line else shift.hour_to
            crosses_midnight = (
                weekday_line.crosses_midnight if weekday_line else shift.crosses_midnight
            )

            h_from = int(hour_from)
            m_from = int(round((hour_from - h_from) * 60))
            local_start = user_tz.localize(
                datetime.combine(rec.work_date, datetime.min.time().replace(hour=h_from, minute=m_from))
            )

            if crosses_midnight:
                end_date = rec.work_date + timedelta(days=1)
            else:
                end_date = rec.work_date

            h_to = int(hour_to)
            m_to = int(round((hour_to - h_to) * 60))
            local_end = user_tz.localize(
                datetime.combine(end_date, datetime.min.time().replace(hour=h_to, minute=m_to))
            )

            rec.planned_start = local_start.astimezone(pytz.utc).replace(tzinfo=None)
            rec.planned_end = local_end.astimezone(pytz.utc).replace(tzinfo=None)

    @api.depends('work_date')
    def _compute_day_type(self):
        """Detecta si la fecha es domingo o festivo usando hr.days.off.year / hr.day.off."""
        for rec in self:
            if not rec.work_date:
                rec.is_sunday = False
                rec.is_holiday = False
                continue
            rec.is_sunday = rec.work_date.weekday() == 6
            # Buscar en hr.day.off (calendario festivo colombiano de la nómina CO)
            holiday = self.env['hr.day.off'].search([
                ('date', '=', rec.work_date),
            ], limit=1)
            rec.is_holiday = bool(holiday)

    @api.constrains('employee_id', 'work_date', 'schedule_id')
    def _check_no_duplicate_assignment(self):
        for rec in self:
            domain = [
                ('employee_id', '=', rec.employee_id.id),
                ('work_date', '=', rec.work_date),
                ('id', '!=', rec.id),
                ('schedule_id.state', 'not in', ['cancel']),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(
                    'El empleado %s ya tiene un turno asignado para el %s en otra programación activa.' % (
                        rec.employee_id.name, rec.work_date,
                    )
                )

    @api.constrains('shift_id', 'work_date')
    def _check_shift_applies_on_date(self):
        for rec in self:
            if rec.shift_id and rec.work_date and not rec.shift_id.applies_on_date(rec.work_date):
                raise ValidationError(
                    'El turno %s no tiene un horario configurado para el día seleccionado.'
                    % rec.shift_id.display_name
                )

    def action_process_attendance(self):
        """Busca la marcación biométrica y genera el registro de asistencia."""
        AttendanceRecord = self.env['hr.attendance.record']
        for line in self:
            if not line.planned_start or not line.planned_end:
                continue
            # Buscar si ya existe un registro para este día/empleado
            existing = AttendanceRecord.search([
                ('employee_id', '=', line.employee_id.id),
                ('schedule_line_id', '=', line.id),
            ], limit=1)
            if existing:
                record = existing
                # Actualizar siempre datos derivados de la línea por si el turno cambió
                record.write({
                    'shift_id': line.shift_id.id,
                    'work_date': line.work_date,
                    'planned_start': line.planned_start,
                    'planned_end': line.planned_end,
                    'is_sunday': line.is_sunday,
                    'is_holiday': line.is_holiday,
                })
            else:
                record = AttendanceRecord.create({
                    'employee_id': line.employee_id.id,
                    'schedule_line_id': line.id,
                    'shift_id': line.shift_id.id,
                    'work_date': line.work_date,
                    'planned_start': line.planned_start,
                    'planned_end': line.planned_end,
                    'is_sunday': line.is_sunday,
                    'is_holiday': line.is_holiday,
                })

            record.action_compute_from_biometric()
            line.attendance_record_id = record
            line.state = line._get_state_from_attendance_result(record.attendance_result)

    def _get_state_from_attendance_result(self, attendance_result):
        """Mapea el resultado detallado al estado simple de la línea."""
        if attendance_result == 'total_absence':
            return 'absent'
        if attendance_result == 'ok':
            return 'processed'
        return 'novelty'

    def _cron_process_daily_attendance(self):
        """Llamado por el cron diario para procesar las marcaciones del día anterior."""
        yesterday = fields.Date.today() - timedelta(days=1)
        lines = self.search([
            ('work_date', '=', yesterday),
            ('schedule_id.state', '=', 'confirmed'),
            ('state', '=', 'scheduled'),
        ])
        if lines:
            lines.action_process_attendance()
