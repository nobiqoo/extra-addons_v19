# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time as dt_time
import pytz

# ── Constantes de legislación laboral colombiana ──────────────────────────────
BOGOTA_TZ = 'America/Bogota'
DAY_START_H = 6    # 06:00 → inicio jornada diurna
NIGHT_START_H = 21  # 21:00 → inicio jornada nocturna
DAILY_OVERTIME_LIMIT = 2.0
WEEKLY_OVERTIME_LIMIT = 12.0

ATTENDANCE_RESULT = [
    ('ok', 'Asistencia Correcta'),
    ('late_minor', 'Retardo Leve'),
    ('late_major', 'Retardo Grave'),
    ('partial_absence', 'Ausencia Parcial'),
    ('total_absence', 'Ausencia Total'),
    ('biometric_issue', 'Inconsistencia Biométrica'),
    ('extra_hours', 'Horas Adicionales'),
]


def _split_day_night(start_local, end_local, day_start_h=DAY_START_H, night_start_h=NIGHT_START_H):
    """Divide el intervalo [start_local, end_local] en porciones diurna y nocturna.

    Ambos parámetros deben ser datetime tz-aware en la misma zona horaria.
    day_start_h / night_start_h son configurables; por defecto usan las constantes
    del módulo (06:00 / 19:00 según Ley 2101/2021).
    Retorna (day_hours, night_hours) como floats.
    """
    if not start_local or not end_local or end_local <= start_local:
        return 0.0, 0.0

    day_secs = 0.0
    night_secs = 0.0
    current = start_local

    while current < end_local:
        # Procesar en fragmentos de hasta 1 día calendario
        next_midnight = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        chunk_end = min(end_local, next_midnight)
        chunk_total = (chunk_end - current).total_seconds()

        d = current.date()
        tz = current.tzinfo
        dsh = int(day_start_h)
        dsh_m = int(round((day_start_h - dsh) * 60))
        nsh = int(night_start_h)
        nsh_m = int(round((night_start_h - nsh) * 60))
        band_day_start = tz.localize(datetime.combine(d, dt_time(dsh, dsh_m))) \
            if hasattr(tz, 'localize') else \
            datetime.combine(d, dt_time(dsh, dsh_m)).replace(tzinfo=tz)
        band_day_end = tz.localize(datetime.combine(d, dt_time(nsh, nsh_m))) \
            if hasattr(tz, 'localize') else \
            datetime.combine(d, dt_time(nsh, nsh_m)).replace(tzinfo=tz)

        seg_start = max(current, band_day_start)
        seg_end = min(chunk_end, band_day_end)
        day_in_chunk = max(0.0, (seg_end - seg_start).total_seconds()) if seg_end > seg_start else 0.0

        day_secs += day_in_chunk
        night_secs += chunk_total - day_in_chunk

        current = chunk_end

    return day_secs / 3600.0, night_secs / 3600.0

CORRECTION_STATE = [
    ('none', 'Sin Corrección'),
    ('requested', 'Solicitud'),
    ('review', 'Revisión'),
    ('approved', 'Aprobado'),
    ('rejected', 'Rechazado'),
    ('applied', 'Aplicado'),
]


class HrAttendanceRecord(models.Model):
    """Registro de asistencia procesado: turno programado vs. marcación real."""
    _name = 'hr.attendance.record'
    _description = 'Registro de Asistencia Biométrica'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'work_date desc, employee_id'

    @api.depends('employee_id', 'work_date', 'shift_id', 'attendance_result')
    def _compute_display_name(self):
        result_labels = dict(ATTENDANCE_RESULT)
        for rec in self:
            employee_name = rec.employee_id.name or 'Sin empleado'
            work_date = fields.Date.to_string(rec.work_date) if rec.work_date else 'Sin fecha'
            shift_name = rec.shift_id.display_name or 'Sin turno'
            result = result_labels.get(rec.attendance_result, rec.attendance_result or 'Sin resultado')
            rec.display_name = '%s - %s - %s (%s)' % (employee_name, work_date, shift_name, result)

    # ─── Identificación ───────────────────────────────────────────────────────
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, index=True, tracking=True,
    )
    schedule_line_id = fields.Many2one(
        'hr.shift.schedule.line',
        string='Línea de Programación',
        ondelete='set null',
        index=True,
    )
    shift_id = fields.Many2one('hr.shift', string='Turno', required=True)
    work_date = fields.Date(string='Fecha', required=True, index=True)

    company_id = fields.Many2one(
        'res.company',
        related='employee_id.company_id',
        store=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        related='employee_id.department_id',
        store=True,
    )
    address_id = fields.Many2one(
        'res.partner',
        string='Sede',
        related='schedule_line_id.address_id',
        store=True,
    )

    # ─── Turno Programado ─────────────────────────────────────────────────────
    planned_start = fields.Datetime(string='Entrada Programada', required=True)
    planned_end = fields.Datetime(string='Salida Programada', required=True)
    planned_hours = fields.Float(
        string='Horas Programadas',
        compute='_compute_planned_hours',
        store=True,
    )

    is_sunday = fields.Boolean(string='Dominical', default=False)
    is_holiday = fields.Boolean(string='Festivo', default=False)

    # ─── Marcación Real (biométrico – fuente: daily.attendance) ──────────────
    actual_check_in = fields.Datetime(string='Entrada Real', tracking=True)
    actual_check_out = fields.Datetime(string='Salida Real', tracking=True)
    worked_hours = fields.Float(
        string='Horas Trabajadas',
        compute='_compute_worked_hours',
        store=True,
    )
    biometric_punch_count = fields.Integer(
        string='Marcaciones',
        default=0,
        help='Cantidad de registros biométricos del día (daily.attendance.punch_count)',
    )

    # ─── Desglose de horas (legislación laboral colombiana) ──────────────────
    day_hours = fields.Float(
        string='Horas Diurnas (06-21)',
        compute='_compute_hour_breakdown',
        store=True,
        digits=(16, 2),
        help='Horas trabajadas dentro de la jornada diurna (06:00-21:00) en el turno.',
    )
    night_hours = fields.Float(
        string='Horas Nocturnas (21-06)',
        compute='_compute_hour_breakdown',
        store=True,
        digits=(16, 2),
        help='Horas con recargo nocturno trabajadas dentro del turno planificado.',
    )
    extra_day_hours = fields.Float(
        string='H.E. Diurnas',
        compute='_compute_hour_breakdown',
        store=True,
        digits=(16, 6),
        help='Horas extras en jornada diurna (más allá del turno planificado).',
    )
    extra_night_hours = fields.Float(
        string='H.E. Nocturnas',
        compute='_compute_hour_breakdown',
        store=True,
        digits=(16, 6),
        help='Horas extras en jornada nocturna (más allá del turno planificado).',
    )
    holiday_work_hours = fields.Float(
        string='Horas Festivo/Dom.',
        compute='_compute_hour_breakdown',
        store=True,
        digits=(16, 2),
        help='Total horas trabajadas en día festivo o dominical.',
    )

    # ─── Valorización económica ────────────────────────────────────────────────
    hour_base_value = fields.Float(
        string='Valor Hora Base',
        compute='_compute_economic_values',
        store=True,
        digits=(16, 2),
        help='Valor de la hora diurna (salario / MAX_HOURS_WORK vigente).',
    )
    night_surcharge_value = fields.Float(
        string='Valor Recargo Nocturno',
        compute='_compute_economic_values',
        store=True,
        digits=(16, 2),
    )
    extra_day_value = fields.Float(
        string='Valor H.E. Diurnas',
        compute='_compute_economic_values',
        store=True,
        digits=(16, 2),
    )
    extra_night_value = fields.Float(
        string='Valor H.E. Nocturnas',
        compute='_compute_economic_values',
        store=True,
        digits=(16, 2),
    )
    holiday_extra_value = fields.Float(
        string='Valor Festivo/Dom.',
        compute='_compute_economic_values',
        store=True,
        digits=(16, 2),
    )
    total_overtime_value = fields.Float(
        string='Total Valor Extras',
        compute='_compute_economic_values',
        store=True,
        digits=(16, 2),
    )

    # ─── Resultado del Análisis ───────────────────────────────────────────────
    attendance_result = fields.Selection(
        selection=ATTENDANCE_RESULT,
        string='Resultado',
        default='total_absence',
        tracking=True,
    )

    delay_minutes = fields.Integer(
        string='Minutos Tardanza',
        compute='_compute_attendance_analysis',
        store=True,
    )
    early_out_minutes = fields.Integer(
        string='Minutos Salida Anticipada',
        compute='_compute_attendance_analysis',
        store=True,
    )
    extra_hours = fields.Float(
        string='Total H.E. Calculadas',
        compute='_compute_attendance_analysis',
        store=True,
    )
    weekly_extra_hours = fields.Float(
        string='H.E. Semana',
        compute='_compute_overtime_limit_alert',
        digits=(16, 2),
        help='Horas extra acumuladas de lunes a domingo para el empleado.',
    )
    overtime_limit_alert = fields.Boolean(
        string='Alerta Límite H.E.',
        compute='_compute_overtime_limit_alert',
    )
    overtime_limit_message = fields.Char(
        string='Alerta de Horas Extra',
        compute='_compute_overtime_limit_alert',
    )

    # ─── Novedades generadas ──────────────────────────────────────────────────
    novelty_ids = fields.One2many(
        'hr.attendance.novelty',
        'attendance_record_id',
        string='Novedades',
    )
    novelty_count = fields.Integer(
        string='# Novedades',
        compute='_compute_novelty_count',
    )

    # ─── Corrección ───────────────────────────────────────────────────────────
    correction_state = fields.Selection(
        selection=CORRECTION_STATE,
        string='Estado Corrección',
        default='none',
        tracking=True,
    )
    correction_reason = fields.Text(string='Motivo de Corrección')
    correction_approved_by = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
    )
    correction_date = fields.Date(string='Fecha Aprobación', readonly=True)

    notes = fields.Text(string='Observaciones')

    # ─── Computadas básicas ───────────────────────────────────────────────────
    @api.depends('planned_start', 'planned_end')
    def _compute_planned_hours(self):
        for rec in self:
            if rec.planned_start and rec.planned_end:
                delta = rec.planned_end - rec.planned_start
                rec.planned_hours = delta.total_seconds() / 3600.0
            else:
                rec.planned_hours = 0.0

    @api.depends('actual_check_in', 'actual_check_out')
    def _compute_worked_hours(self):
        for rec in self:
            if rec.actual_check_in and rec.actual_check_out:
                delta = rec.actual_check_out - rec.actual_check_in
                rec.worked_hours = max(0.0, delta.total_seconds() / 3600.0)
            else:
                rec.worked_hours = 0.0

    @api.depends(
        'actual_check_in', 'actual_check_out',
        'planned_start', 'planned_end',
        'shift_id.tolerance_in', 'shift_id.tolerance_out',
        'shift_id.apply_overtime_tolerance',
        'company_id.overtime_tolerance_minutes',
        'worked_hours', 'planned_hours',
    )
    def _compute_attendance_analysis(self):
        for rec in self:
            delay = 0
            early_out = 0
            extra = 0.0

            if rec.actual_check_in and rec.planned_start:
                diff_in = (rec.actual_check_in - rec.planned_start).total_seconds() / 60.0
                tol_in = rec.shift_id.tolerance_in if rec.shift_id else 5
                if diff_in > tol_in:
                    delay = int(diff_in)

            if rec.actual_check_out and rec.planned_end:
                diff_out = (rec.planned_end - rec.actual_check_out).total_seconds() / 60.0
                tol_out = rec.shift_id.tolerance_out if rec.shift_id else 5
                if diff_out > tol_out:
                    early_out = int(diff_out)

            if rec._is_overtime_above_tolerance():
                overtime_start = rec._get_payable_overtime_start()
                extra = (rec.actual_check_out - overtime_start).total_seconds() / 3600.0

            rec.delay_minutes = delay
            rec.early_out_minutes = early_out
            rec.extra_hours = extra

    def _get_overtime_start(self):
        """Obtiene el fin efectivo, compensando el retraso de entrada."""
        self.ensure_one()
        if not self.planned_end:
            return False

        entry_delay_seconds = 0.0
        if self.actual_check_in and self.planned_start:
            entry_delay_seconds = max(
                (self.actual_check_in - self.planned_start).total_seconds(),
                0.0,
            )
        return self.planned_end + timedelta(seconds=entry_delay_seconds)

    def _get_payable_overtime_start(self):
        """Obtiene el inicio liquidable de HE después de compensar la tardanza."""
        self.ensure_one()
        return self._get_overtime_start()

    def _is_overtime_above_tolerance(self):
        """Valida si existe tiempo liquidable después del fin efectivo."""
        self.ensure_one()
        overtime_start = self._get_payable_overtime_start()
        if not self.actual_check_out or not overtime_start:
            return False

        overtime_minutes = (
            self.actual_check_out - overtime_start
        ).total_seconds() / 60.0
        tolerance_minutes = 0
        if self.shift_id and self.shift_id.apply_overtime_tolerance:
            tolerance_minutes = max(self.shift_id.tolerance_out or 0, 0)
        company_minimum = max(self.company_id.overtime_tolerance_minutes, 0)
        return overtime_minutes > tolerance_minutes and overtime_minutes >= company_minimum

    @api.depends('employee_id', 'work_date', 'extra_hours')
    def _compute_overtime_limit_alert(self):
        """Advierte excesos de 2 horas diarias o 12 horas semanales."""
        weekly_records_by_period = {}

        for rec in self:
            rec.weekly_extra_hours = max(rec.extra_hours or 0.0, 0.0)
            rec.overtime_limit_alert = False
            rec.overtime_limit_message = False

            if not rec.employee_id or not rec.work_date:
                continue

            week_start = rec.work_date - timedelta(days=rec.work_date.weekday())
            week_end = week_start + timedelta(days=6)
            period_key = (rec.employee_id.id, week_start, week_end)

            if period_key not in weekly_records_by_period:
                weekly_records_by_period[period_key] = self.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('work_date', '>=', week_start),
                    ('work_date', '<=', week_end),
                ])

            weekly_records = weekly_records_by_period[period_key]
            weekly_total = sum(max(item.extra_hours or 0.0, 0.0) for item in weekly_records)
            daily_total = sum(
                max(item.extra_hours or 0.0, 0.0)
                for item in weekly_records
                if item.work_date == rec.work_date
            )
            if not rec.id or rec not in weekly_records:
                weekly_total += max(rec.extra_hours or 0.0, 0.0)
                daily_total += max(rec.extra_hours or 0.0, 0.0)

            daily_exceeded = daily_total > DAILY_OVERTIME_LIMIT
            weekly_exceeded = weekly_total > WEEKLY_OVERTIME_LIMIT

            rec.weekly_extra_hours = round(weekly_total, 4)
            rec.overtime_limit_alert = daily_exceeded or weekly_exceeded

            messages = []
            if daily_exceeded:
                messages.append(
                    'supera el límite diario de 2 horas (%.2f h)' % daily_total
                )
            if weekly_exceeded:
                messages.append(
                    'supera el límite semanal de 12 horas (%.2f h)' % weekly_total
                )
            if messages:
                rec.overtime_limit_message = 'Alerta: ' + '; '.join(messages) + '.'

    @api.depends(
        'actual_check_in', 'actual_check_out',
        'planned_start', 'planned_end',
        'is_sunday', 'is_holiday',
        'shift_id.tolerance_out', 'shift_id.apply_overtime_tolerance',
        'company_id.overtime_tolerance_minutes',
    )
    def _compute_hour_breakdown(self):
        """Desglosa las horas trabajadas en diurnas/nocturnas según legislación colombiana.
        Los límites diurno/nocturno se toman de las reglas hr.overtime.rule configuradas;
        si no hay reglas, se usan las constantes por defecto (06:00 / 19:00).
        """
        bogota_tz = pytz.timezone(BOGOTA_TZ)
        utc = pytz.utc

        # Obtener boundaries una sola vez para el lote (optimización de DB queries)
        day_start_h, night_start_h = self[0]._get_time_boundaries() if self else (DAY_START_H, NIGHT_START_H)

        for rec in self:
            if not rec.actual_check_in or not rec.actual_check_out:
                rec.day_hours = 0.0
                rec.night_hours = 0.0
                rec.extra_day_hours = 0.0
                rec.extra_night_hours = 0.0
                rec.holiday_work_hours = 0.0
                continue

            ci_utc = rec.actual_check_in.replace(tzinfo=utc)
            co_utc = rec.actual_check_out.replace(tzinfo=utc)
            ci_local = ci_utc.astimezone(bogota_tz)
            co_local = co_utc.astimezone(bogota_tz)

            # El fin efectivo se desplaza por el retraso de entrada para que el
            # tiempo usado en completar la jornada no se liquide como extra.
            overtime_start = rec._get_overtime_start()
            if overtime_start:
                overtime_start_utc = overtime_start.replace(tzinfo=utc)
                overtime_start_local = overtime_start_utc.astimezone(bogota_tz)
            else:
                overtime_start_local = co_local

            # Porción regular: entrada real → fin efectivo.
            regular_end_local = min(co_local, overtime_start_local)
            reg_day, reg_night = _split_day_night(ci_local, regular_end_local, day_start_h, night_start_h)

            # HED y HEN: aplican después del fin efectivo hasta la salida real.
            # La regla HED (6:00-19:00) cubre la porción diurna del overtime y HEN
            # (19:00-6:00) la nocturna; _compute_hours_by_rules las separa automáticamente.
            ext_day = 0.0
            ext_night = 0.0
            if (
                not (rec.is_sunday or rec.is_holiday)
                and co_local > overtime_start_local
                and rec._is_overtime_above_tolerance()
            ):
                payable_overtime_start = rec._get_payable_overtime_start()
                post_shift_map = rec._compute_hours_by_rules(
                    payable_overtime_start, rec.actual_check_out,
                    is_holiday_sunday=False, is_overtime=True,
                )
                for _ot_type_id, (qty, novelty_type) in post_shift_map.items():
                    if novelty_type == 'extra_day_hours':
                        ext_day += qty
                    elif novelty_type == 'extra_night_hours':
                        ext_night += qty

            # Horas regulares y extras usan intervalos disjuntos, no se restan.
            rec.day_hours = round(reg_day, 4)
            rec.night_hours = round(reg_night, 4)
            rec.extra_day_hours = round(ext_day, 6)
            rec.extra_night_hours = round(ext_night, 6)
            # Horas festivo/dominical = total trabajado si el día aplica
            rec.holiday_work_hours = round(
                rec.worked_hours if (rec.is_sunday or rec.is_holiday) else 0.0, 4
            )

    @api.depends(
        'day_hours', 'night_hours', 'extra_day_hours', 'extra_night_hours',
        'holiday_work_hours', 'is_sunday', 'is_holiday',
        'actual_check_in', 'actual_check_out', 'planned_end',
        'employee_id', 'work_date',
    )
    def _compute_economic_values(self):
        """Valoriza las horas según variables económicas HD/HN/RN o salario/240 como fallback.

        Para días festivos/dominicales se usan reglas holiday_sunday con prioridad
        por rangos específicos y respaldo en reglas amplias.
        Para días normales con extras se usan las reglas HED/HEN correspondientes.
        """
        for rec in self:
            base_val = rec._get_hour_base_value()
            rec.hour_base_value = base_val

            # Recargo nocturno = 35% del valor hora base * horas nocturnas del turno
            rec.night_surcharge_value = round(rec.night_hours * base_val * 0.35, 2)

            if rec.is_sunday or rec.is_holiday:
                # --- Festivo / Dominical ---
                # Las reglas específicas de festivo/dominical tienen prioridad
                # sobre reglas amplias 00:00-24:00 para evitar doble conteo.
                rec.extra_day_value = 0.0
                rec.extra_night_value = 0.0
                if rec.actual_check_in and rec.actual_check_out:
                    hours_map = rec._compute_holiday_hours_by_priority(
                        rec.actual_check_in, rec.actual_check_out)
                    hedf_val = 0.0
                    for ot_type_id, (qty, _nov_type) in hours_map.items():
                        ot_type = rec.env['hr.overtime.type'].browse(ot_type_id)
                        rate = rec._normalize_overtime_rate(ot_type.rate) if ot_type.rate else 1.75
                        hedf_val += round(qty * base_val * rate, 2)
                    rec.holiday_extra_value = hedf_val
                else:
                    rec.holiday_extra_value = 0.0
            else:
                # --- Día normal: buscar la variable económica de la regla correspondiente ---
                company_id = rec.company_id.id if rec.company_id else rec.env.company.id
                normal_rules = rec.env['hr.overtime.rule'].search([
                    ('active', '=', True),
                    ('apply_on', '=', 'normal'),
                    ('is_overtime', '=', True),
                    ('company_id', 'in', [company_id, False]),
                ], order='sequence, id')
                hed_rule = next((r for r in normal_rules if r.hour_from < r.hour_to), None)
                hen_rule = next((r for r in normal_rules if r.hour_from > r.hour_to), None)

                hed_type = rec._get_overtime_type_by_code('HED')
                hed_rate = rec._normalize_overtime_rate(hed_type.rate) if hed_type and hed_type.rate else 1.25
                rec.extra_day_value = round(rec.extra_day_hours * base_val * hed_rate, 2)

                hen_type = rec._get_overtime_type_by_code('HEN')
                hen_rate = rec._normalize_overtime_rate(hen_type.rate) if hen_type and hen_type.rate else 1.75
                rec.extra_night_value = round(rec.extra_night_hours * base_val * hen_rate, 2)

                rec.holiday_extra_value = 0.0

            rec.total_overtime_value = round(
                rec.night_surcharge_value
                + rec.extra_day_value
                + rec.extra_night_value
                + rec.holiday_extra_value,
                2,
            )

    @api.depends('novelty_ids')
    def _compute_novelty_count(self):
        for rec in self:
            rec.novelty_count = len(rec.novelty_ids)

    # ─── Helpers de valorización ──────────────────────────────────────────────
    def _get_hour_base_value(self):
        """Retorna el valor monetario de 1 hora diurna.

        Orden de búsqueda:
        1. Salario del contrato / MAX_HOURS_WORK vigente en el año de trabajo.
        2. Variable económica con código 'HD' vigente en el mismo año.
        3. Fallback: SMMLV / MAX_HOURS_WORK vigente en el mismo año.
        4. Fallback final: salario del contrato activo / 240.

        Si una variable tiene varias líneas en el año, se usa la del mes más
        reciente que no sea posterior al mes de la asistencia.
        """
        self.ensure_one()
        if not self.work_date:
            return 0.0

        year_str = str(self.work_date.year)

        def _latest_variable_line(code):
            return self.env['economic.variable.line'].search([
                ('variable_code', '=', code),
                ('year', '=', year_str),
                ('month_int', '<=', self.work_date.month),
            ], order='month_int desc, id desc', limit=1)

        contract = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'open'),
        ], order='date_start desc, id desc', limit=1)
        hours_line = _latest_variable_line('MAX_HOURS_WORK')

        # 1. Salario real del empleado / horas mensuales vigentes.
        if contract and contract.wage and hours_line and hours_line.value:
            return contract.wage / hours_line.value

        # 2. Buscar variable HD vigente en el año.
        hd_line = _latest_variable_line('HD')
        if hd_line and hd_line.value:
            return hd_line.value

        # 3. SMMLV / MAX_HOURS_WORK vigentes en el año.
        smmlv_line = _latest_variable_line('SMMLV')
        if smmlv_line and smmlv_line.value and hours_line and hours_line.value:
            return smmlv_line.value / hours_line.value

        # 4. Compatibilidad si el año no tiene MAX_HOURS_WORK configurado.
        if contract and contract.wage:
            return contract.wage / 240.0

        return 0.0

    def _get_overtime_type_by_code(self, code):
        """Busca hr.overtime.type por código en la compañía actual o sin compañía."""
        company_id = self.company_id.id if self.company_id else self.env.company.id
        ot_type = self.env['hr.overtime.type'].search([
            ('code', '=', code),
            ('company_id', '=', company_id),
        ], limit=1)
        if not ot_type:
            ot_type = self.env['hr.overtime.type'].search([
                ('code', '=', code),
                ('company_id', '=', False),
            ], limit=1)
        return ot_type

    def _normalize_overtime_rate(self, rate):
        return rate / 100.0 if rate and rate > 10.0 else rate

    def _get_time_boundaries(self):
        """Obtiene (day_start_h, night_start_h) desde las reglas hr.overtime.rule configuradas.

        Prefiere la regla de recargo nocturno (normal + is_overtime=False), porque
        esa regla define la frontera real entre jornada diurna y nocturna. Si no
        existe, usa las constantes legales por defecto del módulo.
        """
        company_id = self.company_id.id if self.company_id else self.env.company.id
        night_rule = self.env['hr.overtime.rule'].search([
            ('active', '=', True),
            ('apply_on', '=', 'normal'),
            ('is_overtime', '=', False),
            ('company_id', 'in', [company_id, False]),
        ], order='sequence, id')
        for rule in night_rule:
            if rule.hour_from > rule.hour_to:  # noche: 19:00 → 06:00
                return rule.hour_to, rule.hour_from
        return float(DAY_START_H), float(NIGHT_START_H)

    def _compute_hours_by_rules(self, start_utc, end_utc, is_holiday_sunday, is_overtime):
        """Calcula las horas del intervalo [start_utc, end_utc] clasificadas por tipo
        de hora extra, según las reglas hr.overtime.rule configuradas.

        start_utc / end_utc son datetimes sin timezone (UTC, como los almacena Odoo).
        Devuelve dict {overtime_type_id (int): float horas} con las coincidencias.
        Horas no cubiertas por ninguna regla se ignoran (se genera advertencia).
        """
        self.ensure_one()
        if not start_utc or not end_utc or end_utc <= start_utc:
            return {}

        bogota_tz = pytz.timezone(BOGOTA_TZ)
        utc = pytz.utc
        start_local = start_utc.replace(tzinfo=utc).astimezone(bogota_tz)
        end_local = end_utc.replace(tzinfo=utc).astimezone(bogota_tz)

        company_id = self.company_id.id if self.company_id else self.env.company.id
        apply_on = 'holiday_sunday' if is_holiday_sunday else 'normal'

        rules = self.env['hr.overtime.rule'].search([
            ('active', '=', True),
            ('is_overtime', '=', is_overtime),
            ('apply_on', '=', apply_on),
            ('company_id', 'in', [company_id, False]),
        ], order='sequence, id')

        result = {}
        current = start_local

        while current < end_local:
            next_midnight = (current + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            chunk_end = min(end_local, next_midnight)

            for rule in rules:
                h = rule._compute_overlap_hours(current, chunk_end)
                if h > 0:
                    ot_id = rule.overtime_type_id.id
                    nov_type = rule.novelty_type or 'extra_hours'
                    if ot_id in result:
                        # Acumular horas; mantener novelty_type del primer match
                        result[ot_id] = (result[ot_id][0] + h, result[ot_id][1] or nov_type)
                    else:
                        result[ot_id] = (h, nov_type)

            current = chunk_end

        return result

    def _rule_hour_to_local_dt(self, day, tz, hour_value):
        """Convierte una hora float de regla a datetime local tz-aware."""
        hour_value = max(0.0, min(float(hour_value or 0.0), 24.0))
        total_min = int(round(hour_value * 60))
        if total_min >= 24 * 60:
            base = datetime.combine(day + timedelta(days=1), dt_time(0, 0))
        else:
            base = datetime.combine(
                day,
                dt_time(total_min // 60, total_min % 60),
            )
        return tz.localize(base) if hasattr(tz, 'localize') else base.replace(tzinfo=tz)

    def _add_rule_boundaries(self, boundaries, rule, day, tz):
        """Agrega cortes horarios para trocear el día según la configuración."""
        boundaries.add(self._rule_hour_to_local_dt(day, tz, rule.hour_from))
        boundaries.add(self._rule_hour_to_local_dt(day, tz, rule.hour_to))
        if rule.hour_from > rule.hour_to:
            boundaries.add(self._rule_hour_to_local_dt(day, tz, 0.0))
            boundaries.add(self._rule_hour_to_local_dt(day, tz, 24.0))

    def _compute_holiday_hours_by_priority(self, start_utc, end_utc):
        """Clasifica horas dominicales/festivas priorizando reglas específicas.

        Primero evalúa reglas holiday_sunday con "Solo Horas Extras" desmarcado
        y usa reglas marcadas como horas extra solo para los intervalos no cubiertos.
        """
        self.ensure_one()
        if not start_utc or not end_utc or end_utc <= start_utc:
            return {}

        bogota_tz = pytz.timezone(BOGOTA_TZ)
        utc = pytz.utc
        start_local = start_utc.replace(tzinfo=utc).astimezone(bogota_tz)
        end_local = end_utc.replace(tzinfo=utc).astimezone(bogota_tz)

        company_id = self.company_id.id if self.company_id else self.env.company.id
        rules = self.env['hr.overtime.rule'].search([
            ('active', '=', True),
            ('apply_on', '=', 'holiday_sunday'),
            ('company_id', 'in', [company_id, False]),
        ], order='sequence, id')
        primary_rules = rules.filtered(lambda rule: not rule.is_overtime)
        fallback_rules = rules.filtered(lambda rule: rule.is_overtime)

        result = {}
        current = start_local
        while current < end_local:
            next_midnight = (current + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            chunk_end = min(end_local, next_midnight)

            boundaries = {current, chunk_end}
            for rule in primary_rules | fallback_rules:
                self._add_rule_boundaries(boundaries, rule, current.date(), current.tzinfo)
            ordered = sorted(point for point in boundaries if current <= point <= chunk_end)

            for index in range(len(ordered) - 1):
                segment_start = ordered[index]
                segment_end = ordered[index + 1]
                if segment_end <= segment_start:
                    continue

                selected_rule = False
                for rule_group in (primary_rules, fallback_rules):
                    selected_rule = next((
                        rule for rule in rule_group
                        if rule._compute_overlap_hours(segment_start, segment_end) > 0
                    ), False)
                    if selected_rule:
                        break

                if not selected_rule:
                    continue

                qty = (segment_end - segment_start).total_seconds() / 3600.0
                ot_id = selected_rule.overtime_type_id.id
                novelty_type = selected_rule.novelty_type or 'compensatory'
                if ot_id in result:
                    result[ot_id] = (result[ot_id][0] + qty, result[ot_id][1])
                else:
                    result[ot_id] = (qty, novelty_type)

            current = chunk_end

        return result

    # ─── Lógica principal ─────────────────────────────────────────────────────
    def action_compute_from_biometric(self):
        """Lee la vista daily.attendance y calcula el resultado de asistencia.

        La vista daily.attendance (de hr_zk_attendance) agrega automáticamente
        todas las marcaciones del día por empleado, exponiendo check_in (primera
        marcación) y check_out (última marcación). Para turnos que cruzan la
        medianoche se usa una ventana local de 12:00 del día de trabajo a 12:00
        del día siguiente, evitando que la salida quede separada de la entrada.
        """
        DailyAttendance = self.env['daily.attendance']
        BiometricAttendance = self.env['zk.machine.attendance']
        for rec in self:
            if not rec.planned_start or not rec.planned_end:
                continue

            shift = rec.shift_id
            weekday_line = shift.get_weekday_line(rec.work_date) if shift else False
            crosses_midnight = (
                weekday_line.crosses_midnight
                if weekday_line else bool(shift and shift.crosses_midnight)
            )

            if crosses_midnight:
                tz_name = rec.employee_id.company_id.partner_id.tz or BOGOTA_TZ
                try:
                    employee_tz = pytz.timezone(tz_name)
                except pytz.UnknownTimeZoneError:
                    employee_tz = pytz.timezone(BOGOTA_TZ)

                local_window_start = employee_tz.localize(
                    datetime.combine(rec.work_date, dt_time(12, 0))
                )
                local_window_end = employee_tz.localize(
                    datetime.combine(rec.work_date + timedelta(days=1), dt_time(12, 0))
                )
                window_start = local_window_start.astimezone(pytz.utc).replace(tzinfo=None)
                window_end = local_window_end.astimezone(pytz.utc).replace(tzinfo=None)

                punches = BiometricAttendance.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('punching_time', '>=', window_start),
                    ('punching_time', '<', window_end),
                ], order='punching_time asc')

                check_in = punches[:1].punching_time if punches else False
                check_out = punches[-1:].punching_time if len(punches) > 1 else False
                punch_count = len(punches)
            else:
                daily = DailyAttendance.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('punching_day', '=', rec.work_date),
                ], limit=1)
                check_in = daily.check_in if daily else False
                check_out = (
                    daily.check_out
                    if daily and daily.check_out != daily.check_in else False
                )
                punch_count = daily.punch_count if daily else 0

            if not check_in:
                rec.actual_check_in = False
                rec.actual_check_out = False
                rec.biometric_punch_count = 0
                rec.attendance_result = 'total_absence'
                rec._generate_novelties()
                continue

            rec.actual_check_in = check_in
            rec.actual_check_out = check_out
            rec.biometric_punch_count = punch_count or 0

            rec.attendance_result = rec._classify_attendance()
            rec._generate_novelties()

    def _classify_attendance(self):
        """Clasifica el resultado según las marcaciones y el turno."""
        self.ensure_one()
        if not self.actual_check_in:
            return 'total_absence'
        if not self.actual_check_out:
            return 'biometric_issue'

        tol_in = (self.shift_id.tolerance_in if self.shift_id else 5) * 60   # en segundos
        tol_out = (self.shift_id.tolerance_out if self.shift_id else 5) * 60

        delay_secs = (self.actual_check_in - self.planned_start).total_seconds()
        early_secs = (self.planned_end - self.actual_check_out).total_seconds()

        # Trabajó menos del 50% de la jornada
        if self.planned_hours > 0 and self.worked_hours < (self.planned_hours * 0.5):
            return 'partial_absence'

        if self.extra_day_hours + self.extra_night_hours > 0:
            return 'extra_hours'

        if delay_secs > tol_in:
            return 'late_major' if delay_secs > 30 * 60 else 'late_minor'

        if early_secs > tol_out:
            return 'partial_absence'

        return 'ok'

    def _generate_novelties(self):
        """Genera o actualiza novedades a partir del análisis de asistencia."""
        self.ensure_one()
        # Limpiar novedades previas no aplicadas
        self.novelty_ids.filtered(lambda n: n.state == 'draft').unlink()

        result = self.attendance_result
        novelties = []

        if result == 'total_absence':
            novelties.append({
                'novelty_type': 'absence',
                'description': 'Ausencia total - sin marcación biométrica',
                'minutes': int(self.planned_hours * 60),
            })
        elif result in ('late_minor', 'late_major'):
            novelties.append({
                'novelty_type': 'delay',
                'description': 'Tardanza de %d minutos' % self.delay_minutes,
                'minutes': self.delay_minutes,
            })
        elif result == 'partial_absence':
            total_min = self.early_out_minutes or int((self.planned_hours - self.worked_hours) * 60)
            novelties.append({
                'novelty_type': 'partial_absence',
                'description': 'Ausencia parcial / salida anticipada (%d min)' % total_min,
                'minutes': total_min,
            })
        elif result == 'extra_hours':
            # Usar reglas configuradas para determinar la categoría de hora extra.
            # HED y HEN se calculan desde el fin efectivo hasta la salida real;
            # _compute_hours_by_rules los separa según la franja horaria de cada regla.
            hours_map = {}

            if self._is_overtime_above_tolerance():
                overtime_start = self._get_payable_overtime_start()
                post_shift_map = self._compute_hours_by_rules(
                    overtime_start, self.actual_check_out,
                    is_holiday_sunday=False, is_overtime=True,
                )
                for ot_type_id, (qty, novelty_type) in post_shift_map.items():
                    if ot_type_id in hours_map:
                        hours_map[ot_type_id] = (hours_map[ot_type_id][0] + qty, hours_map[ot_type_id][1])
                    else:
                        hours_map[ot_type_id] = (qty, novelty_type)

            if not hours_map:
                from odoo.exceptions import UserError
                raise UserError(
                    'No se encontró ninguna regla de horas extras configurada para '
                    'días normales.\nRevise: Control de Turnos → Configuración → '
                    'Reglas de Horas Extras y asegúrese de tener reglas activas '
                    'de tipo "Día Normal" + "Solo Horas Extras".'
                )
            for ot_type_id, (qty, novelty_type) in hours_map.items():
                ot_type = self.env['hr.overtime.type'].browse(ot_type_id)
                nov = {
                    'novelty_type': novelty_type,
                    'overtime_type_id': ot_type.id,
                    'description': 'Horas extras %s (%s): %.4f h' % (
                        ot_type.name, ot_type.code, qty),
                    'extra_hours': round(qty, 4),
                }
                if novelty_type == 'extra_day_hours':
                    nov['extra_day_qty'] = round(qty, 4)
                elif novelty_type == 'extra_night_hours':
                    nov['extra_night_qty'] = round(qty, 4)
                novelties.append(nov)
        elif result == 'biometric_issue':
            novelties.append({
                'novelty_type': 'biometric_issue',
                'description': 'Inconsistencia biométrica - falta marcación de salida',
                'minutes': 0,
            })

        # Recargo nocturno: horas nocturnas trabajadas DENTRO del turno planificado.
        # Se calcula con reglas normal + is_overtime=False para no confundirlo con HEN,
        # que solo aplica a horas nocturnas después de la salida programada.
        if (
            self.actual_check_in and self.actual_check_out
            and self.planned_start and self.planned_end
            and not (self.is_sunday or self.is_holiday)
        ):
            regular_start = max(self.actual_check_in, self.planned_start)
            regular_end = min(self.actual_check_out, self._get_overtime_start())
            if regular_end > regular_start:
                night_surcharge_map = self._compute_hours_by_rules(
                    regular_start, regular_end,
                    is_holiday_sunday=False, is_overtime=False,
                )
                for ot_type_id, (qty, novelty_type) in night_surcharge_map.items():
                    ot_type = self.env['hr.overtime.type'].browse(ot_type_id)
                    novelties.append({
                        'novelty_type': novelty_type,
                        'overtime_type_id': ot_type.id,
                        'description': '%s (%s): %.4f h' % (
                            ot_type.name, ot_type.code, qty),
                        'extra_hours': round(qty, 4),
                        'minutes': int(round(qty * 60)),
                    })

        # Dominical o festivo con trabajo: respeta primero rangos específicos
        # y usa reglas amplias como respaldo para los intervalos no cubiertos.
        # Se procesa independiente del result (puede coincidir con extra_hours en festivo).
        if (self.is_sunday or self.is_holiday) and self.actual_check_in and self.actual_check_out:
            label = 'festivo' if self.is_holiday else 'domingo'
            hours_map = self._compute_holiday_hours_by_priority(
                self.actual_check_in, self.actual_check_out)
            if not hours_map:
                from odoo.exceptions import UserError
                raise UserError(
                    'No se encontró ninguna regla de horas extras configurada para '
                    'días festivos/dominicales.\nRevise: Control de Turnos → Configuración → '
                    'Reglas de Horas Extras y asegúrese de tener reglas activas de tipo '
                    '"Festivo / Dominical".'
                )
            for ot_type_id, (qty, novelty_type) in hours_map.items():
                ot_type = self.env['hr.overtime.type'].browse(ot_type_id)
                novelties.append({
                    'novelty_type': novelty_type,
                    'overtime_type_id': ot_type.id,
                    'description': 'Trabajo en %s - %s (%s): %.4f h' % (
                        label, ot_type.name, ot_type.code, qty),
                    'extra_hours': round(qty, 4),
                    'minutes': int(round(qty * 60)),
                })

        for nov_vals in novelties:
            # Reprocessing must not recreate a reviewed, approved or paid novelty.
            existing = self.novelty_ids.filtered(
                lambda n: n.state != 'draft'
                and n.novelty_type == nov_vals['novelty_type']
                and n.overtime_type_id.id == nov_vals.get('overtime_type_id', False)
            )
            if existing:
                continue
            self.env['hr.attendance.novelty'].create({
                'attendance_record_id': self.id,
                'employee_id': self.employee_id.id,
                'work_date': self.work_date,
                'novelty_type': nov_vals['novelty_type'],
                'description': nov_vals['description'],
                'minutes': nov_vals.get('minutes', 0),
                'extra_hours': nov_vals.get('extra_hours', 0.0),
                'extra_day_qty': nov_vals.get('extra_day_qty', 0.0),
                'extra_night_qty': nov_vals.get('extra_night_qty', 0.0),
                'overtime_type_id': nov_vals.get('overtime_type_id', False),
            })

    def action_request_correction(self):
        self.ensure_one()
        self.correction_state = 'requested'

    def action_approve_correction(self):
        self.ensure_one()
        self.correction_state = 'approved'
        self.correction_approved_by = self.env.user
        self.correction_date = fields.Date.today()
        self.attendance_result = self._classify_attendance()
        self._generate_novelties()

    def action_reject_correction(self):
        self.ensure_one()
        self.correction_state = 'rejected'

    def action_view_novelties(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Novedades',
            'res_model': 'hr.attendance.novelty',
            'view_mode': 'list,form',
            'domain': [('attendance_record_id', '=', self.id)],
        }
