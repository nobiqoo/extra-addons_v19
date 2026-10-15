# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta


class HrProcessAttendanceWizard(models.TransientModel):
    """Wizard para procesar asistencias biométricas en bloque o generar turnos masivos."""
    _name = 'hr.process.attendance.wizard'
    _description = 'Procesar Asistencia Biométrica'

    # ── Modo de operación ──────────────────────────────────────────────────
    action = fields.Selection([
        ('process', 'Procesar marcaciones biométricas'),
        ('generate', 'Generar programación masiva de turnos'),
        ('check_overtime', 'Verificar límites de horas extra'),
    ], string='Acción', required=True, default='process')

    # ── Filtros comunes ────────────────────────────────────────────────────
    date_start = fields.Date(string='Fecha Inicio', required=True, default=fields.Date.today)
    date_end = fields.Date(string='Fecha Fin', required=True, default=fields.Date.today)

    schedule_id = fields.Many2one(
        'hr.shift.schedule',
        string='Programación',
    )
    department_id = fields.Many2one('hr.department', string='Departamento')
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
        help='Dejar vacío para todos los empleados del departamento/programación',
    )

    # ── Solo para generación masiva ─────────────────────────────────────
    shift_id = fields.Many2one(
        'hr.shift',
        string='Turno a Asignar',
    )
    shift_assignment_mode = fields.Selection([
        ('single', 'Un turno para todos'),
        ('by_employee', 'Turno diferente por empleado'),
    ], string='Forma de Asignación', required=True, default='single')
    employee_shift_line_ids = fields.One2many(
        'hr.process.attendance.wizard.line',
        'wizard_id',
        string='Turnos por Empleado',
    )
    exclude_sundays = fields.Boolean(string='Excluir Domingos', default=True)
    exclude_holidays = fields.Boolean(string='Excluir Festivos', default=True)

    # ── Resultados ──────────────────────────────────────────────────────
    result_message = fields.Text(string='Resultado', readonly=True)
    has_overtime_alert = fields.Boolean(
        string='Alerta de Horas Extra',
        readonly=True,
    )
    overtime_alert_message = fields.Text(
        string='Detalle de la Alerta',
        readonly=True,
    )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start > rec.date_end:
                raise ValidationError('La fecha de inicio debe ser anterior a la fecha de fin.')

    @api.onchange('shift_assignment_mode')
    def _onchange_shift_assignment_mode(self):
        if self.shift_assignment_mode == 'by_employee':
            self._sync_employee_shift_lines()
        else:
            self.employee_shift_line_ids = [fields.Command.clear()]

    @api.onchange('employee_ids', 'department_id')
    def _onchange_generation_employees(self):
        if self.action == 'generate' and self.shift_assignment_mode == 'by_employee':
            self._sync_employee_shift_lines()

    @api.onchange('shift_id')
    def _onchange_default_shift(self):
        if self.shift_assignment_mode == 'by_employee' and self.shift_id:
            for line in self.employee_shift_line_ids.filtered(lambda item: not item.shift_id):
                line.shift_id = self.shift_id

    def _sync_employee_shift_lines(self):
        """Carga empleados en la tabla conservando el turno ya seleccionado."""
        self.ensure_one()
        employees = self.employee_ids
        if not employees and self.department_id:
            employees = self.env['hr.employee'].search([
                ('department_id', '=', self.department_id.id),
                ('active', '=', True),
            ])
        if not employees:
            return

        existing_shifts = {
            line.employee_id.id: line.shift_id.id
            for line in self.employee_shift_line_ids
            if line.employee_id and line.shift_id
        }
        self.employee_shift_line_ids = [fields.Command.clear()] + [
            fields.Command.create({
                'employee_id': employee.id,
                'shift_id': existing_shifts.get(employee.id) or self.shift_id.id,
            })
            for employee in employees
        ]

    def action_execute(self):
        self.ensure_one()
        if self.action == 'process':
            return self._do_process_attendance()
        elif self.action == 'generate':
            return self._do_generate_schedule()
        return self._do_check_overtime_limits()

    def _get_overtime_alert_details(self, attendance_records):
        """Construye el detalle de excesos diarios y semanales sin duplicarlos."""
        daily_totals = {}
        weekly_alerts = {}

        for record in attendance_records:
            daily_key = (record.employee_id.id, record.work_date)
            if daily_key not in daily_totals:
                daily_totals[daily_key] = [record.employee_id.name, 0.0]
            daily_totals[daily_key][1] += max(record.extra_hours or 0.0, 0.0)

            if (record.weekly_extra_hours or 0.0) > 12.0:
                week_start = record.work_date - timedelta(days=record.work_date.weekday())
                weekly_alerts[(record.employee_id.id, week_start)] = (
                    record.employee_id.name,
                    record.weekly_extra_hours,
                )

        alert_details = []
        exceeded_days = [
            (employee_id, work_date, values[0], values[1])
            for (employee_id, work_date), values in daily_totals.items()
            if values[1] > 2.0
        ]
        if exceeded_days:
            alert_details.append('Límite diario (máximo 2 horas):')
            for _employee_id, work_date, employee_name, total in sorted(
                exceeded_days, key=lambda item: (item[1], item[2])
            ):
                alert_details.append(
                    '  • %s - %s: %.2f horas extra' % (
                        work_date,
                        employee_name,
                        total,
                    )
                )

        if weekly_alerts:
            if alert_details:
                alert_details.append('')
            alert_details.append('Límite semanal (máximo 12 horas):')
            for (_employee_id, week_start), (employee_name, total) in sorted(
                weekly_alerts.items(), key=lambda item: (item[0][1], item[1][0])
            ):
                week_end = week_start + timedelta(days=6)
                alert_details.append(
                    '  • %s - semana %s a %s: %.2f horas extra' % (
                        employee_name,
                        week_start,
                        week_end,
                        total,
                    )
                )

        return alert_details

    def _show_result(self, title):
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'hr.process.attendance.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _do_process_attendance(self):
        """Procesa las marcaciones biométricas para las líneas de programación en el rango."""
        ScheduleLine = self.env['hr.shift.schedule.line']
        domain = [
            ('work_date', '>=', self.date_start),
            ('work_date', '<=', self.date_end),
            ('schedule_id.state', '=', 'confirmed'),
        ]
        if self.schedule_id:
            domain.append(('schedule_id', '=', self.schedule_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))

        lines = ScheduleLine.search(domain)
        if not lines:
            raise UserError('No se encontraron líneas de programación para los criterios indicados.')

        lines.action_process_attendance()

        ok = lines.filtered(lambda l: l.state == 'processed')
        novelty = lines.filtered(lambda l: l.state == 'novelty')
        absent = lines.filtered(lambda l: l.state == 'absent')
        attendance_records = lines.mapped('attendance_record_id')
        alert_details = self._get_overtime_alert_details(attendance_records)

        self.has_overtime_alert = bool(alert_details)
        self.overtime_alert_message = '\n'.join(alert_details) if alert_details else False

        self.result_message = (
            'Procesamiento completado:\n'
            '  ✓ Correctas: %d\n'
            '  ⚠ Con novedad: %d\n'
            '  ✗ Ausentes: %d\n'
            '  Total: %d'
        ) % (len(ok), len(novelty), len(absent), len(lines))

        return self._show_result('Resultado del Procesamiento')

    def _do_check_overtime_limits(self):
        """Verifica los topes de horas extra usando el período y filtros del wizard."""
        domain = [
            ('work_date', '>=', self.date_start),
            ('work_date', '<=', self.date_end),
        ]
        if self.schedule_id:
            domain.append(('schedule_line_id.schedule_id', '=', self.schedule_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))

        attendance_records = self.env['hr.attendance.record'].search(domain)
        if not attendance_records:
            raise UserError(
                'No se encontraron registros de asistencia para los criterios indicados.'
            )

        alert_details = self._get_overtime_alert_details(attendance_records)
        self.has_overtime_alert = bool(alert_details)
        self.overtime_alert_message = '\n'.join(alert_details) if alert_details else False
        self.result_message = (
            'Verificación completada:\n'
            '  Registros revisados: %d\n'
            '  Resultado: %s'
        ) % (
            len(attendance_records),
            'se encontraron excesos de horas extra'
            if alert_details else 'no se encontraron excesos de horas extra',
        )

        return self._show_result('Resultado de Límites de Horas Extra')

    def _do_generate_schedule(self):
        """Genera líneas de programación masiva con turno general o por empleado."""
        self.has_overtime_alert = False
        self.overtime_alert_message = False
        if self.shift_assignment_mode == 'single' and not self.shift_id:
            raise UserError('Debe seleccionar un turno para la generación masiva.')

        schedule = self.schedule_id
        if not schedule:
            schedule = self.env['hr.shift.schedule'].create({
                'name': 'Programación %s al %s' % (self.date_start, self.date_end),
                'date_start': self.date_start,
                'date_end': self.date_end,
                'department_id': self.department_id.id if self.department_id else False,
            })

        # Obtener la pareja empleado/turno según el modo seleccionado.
        if self.shift_assignment_mode == 'by_employee':
            lines = self.employee_shift_line_ids.filtered(
                lambda line: line.employee_id and line.shift_id
            )
            if not lines:
                raise UserError('Agregue al menos un empleado con su turno.')
            if len(lines.mapped('employee_id')) != len(lines):
                raise UserError('No puede repetir un empleado en las líneas de turnos.')
            assignments = [(line.employee_id, line.shift_id) for line in lines]
        else:
            if self.employee_ids:
                employees = self.employee_ids
            elif self.department_id:
                employees = self.env['hr.employee'].search([
                    ('department_id', '=', self.department_id.id),
                    ('active', '=', True),
                ])
            else:
                raise UserError('Seleccione empleados o un departamento para la generación masiva.')
            assignments = [(employee, self.shift_id) for employee in employees]

        # Obtener festivos en el rango
        holiday_dates = set()
        if self.exclude_holidays:
            holidays = self.env['hr.day.off'].search([
                ('date', '>=', self.date_start),
                ('date', '<=', self.date_end),
            ])
            holiday_dates = set(holidays.mapped('date'))

        created = 0
        skipped = 0
        skipped_by_shift_day = 0
        skipped_sundays = 0
        skipped_holidays = 0
        current = self.date_start
        ScheduleLine = self.env['hr.shift.schedule.line']

        while current <= self.date_end:
            if self.exclude_sundays and current.weekday() == 6:
                skipped_sundays += len(assignments)
                current += timedelta(days=1)
                continue
            if current in holiday_dates:
                skipped_holidays += len(assignments)
                current += timedelta(days=1)
                continue

            for employee, shift in assignments:
                if not shift.applies_on_date(current):
                    skipped_by_shift_day += 1
                    continue
                existing = ScheduleLine.search([
                    ('employee_id', '=', employee.id),
                    ('work_date', '=', current),
                    ('schedule_id.state', 'not in', ['cancel']),
                ], limit=1)
                if existing:
                    skipped += 1
                    continue

                ScheduleLine.create({
                    'schedule_id': schedule.id,
                    'employee_id': employee.id,
                    'shift_id': shift.id,
                    'work_date': current,
                })
                created += 1

            current += timedelta(days=1)

        self.result_message = (
            'Generación completada:\n'
            '  ✓ Líneas creadas: %d\n'
            '  ⚠ Omitidas (ya existían): %d\n'
            '  ⚠ Omitidas (domingos excluidos): %d\n'
            '  ⚠ Omitidas (festivos excluidos): %d\n'
            '  ⚠ Omitidas (día no configurado para el turno): %d\n'
            '  Programación: %s'
        ) % (
            created,
            skipped,
            skipped_sundays,
            skipped_holidays,
            skipped_by_shift_day,
            schedule.name,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Resultado de Generación',
            'res_model': 'hr.process.attendance.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class HrProcessAttendanceWizardLine(models.TransientModel):
    _name = 'hr.process.attendance.wizard.line'
    _description = 'Turno por Empleado en Generación Masiva'
    _order = 'employee_id'

    wizard_id = fields.Many2one(
        'hr.process.attendance.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        related='employee_id.department_id',
        readonly=True,
    )
    shift_id = fields.Many2one(
        'hr.shift',
        string='Turno',
        required=True,
    )
