# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

SHIFT_TYPE = [
    ('day', 'Diurno'),
    ('night', 'Nocturno'),
    ('mixed', 'Mixto'),
    ('rotating', 'Rotativo'),
    ('admin', 'Administrativo'),
    ('special', 'Especial'),
    ('sunday', 'Dominical'),
    ('holiday', 'Festivo'),
    ('extended', 'Extendido'),
    ('twelve', '12 Horas'),
]

WEEKDAY_SELECTION = [
    ('0', 'Lunes'),
    ('1', 'Martes'),
    ('2', 'Miércoles'),
    ('3', 'Jueves'),
    ('4', 'Viernes'),
    ('5', 'Sábado'),
    ('6', 'Domingo'),
]


class HrShift(models.Model):
    _name = 'hr.shift'
    _description = 'Turno Laboral'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, tracking=True)
    code = fields.Char(string='Código', required=True, size=10, tracking=True)

    shift_type = fields.Selection(
        selection=SHIFT_TYPE,
        string='Tipo de Turno',
        required=True,
        default='day',
        tracking=True,
    )

    hour_from = fields.Float(
        string='Hora Inicio',
        required=True,
        help='Hora de inicio del turno (ej. 6.0 = 06:00 AM)',
    )
    hour_to = fields.Float(
        string='Hora Fin',
        required=True,
        help='Hora de fin del turno (ej. 14.0 = 02:00 PM)',
    )

    # Indica si el turno cruza medianoche
    crosses_midnight = fields.Boolean(
        string='Cruza Medianoche',
        compute='_compute_crosses_midnight',
        store=True,
    )

    rest_time = fields.Float(
        string='Tiempo Descanso (h)',
        default=0.5,
        help='Tiempo de descanso/comida en horas (descontado de horas efectivas)',
    )
    effective_hours = fields.Float(
        string='Horas Efectivas',
        compute='_compute_effective_hours',
        store=True,
    )

    tolerance_in = fields.Integer(
        string='Tolerancia Ingreso (min)',
        default=5,
        help='Minutos de gracia para la llegada',
    )
    tolerance_out = fields.Integer(
        string='Tolerancia Salida (min)',
        default=5,
        help='Minutos de gracia para la salida anticipada y para iniciar el cálculo de horas extra',
    )
    apply_overtime_tolerance = fields.Boolean(
        string='Aplicar tolerancia a horas extra',
        default=True,
        help=(
            'Si está marcado, solo se reconocen horas extra cuando el tiempo '
            'adicional supera la tolerancia de salida. Una vez superada, se '
            'reconoce todo el tiempo adicional.'
        ),
    )

    color = fields.Integer(
        string='Color',
        default=0,
        help='Color identificador en el calendario',
    )

    active = fields.Boolean(default=True, tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    # Configuración opcional de un horario diferente para cada día.
    # El modo "all" conserva el comportamiento existente.
    assignment_mode = fields.Selection([
        ('all', 'Horario general'),
        ('weekdays', 'Horario diferente por día'),
    ], string='Tipo de Horario', required=True, default='all', tracking=True)
    weekday_line_ids = fields.One2many(
        'hr.shift.weekday.line',
        'shift_id',
        string='Horarios por Día',
        copy=True,
    )

    # Turno de alargue
    is_extension = fields.Boolean(string='¿Es Turno de Alargue?', default=False)
    extension_hours = fields.Float(
        string='Horas de Extensión',
        default=2.0,
        help='Número de horas de extensión',
    )
    extension_position = fields.Selection([
        ('before', 'Antes del turno'),
        ('after', 'Después del turno'),
    ], string='Posición Extensión', default='after')
    extension_includes_meal = fields.Boolean(
        string='Incluye Tiempo de Comida',
        default=False,
    )

    # Turno rotativo ciclo 21 días (modelo 2x2x2)
    is_rotating_cycle = fields.Boolean(string='¿Ciclo Rotativo 21 Días?', default=False)
    cycle_day_shift_id = fields.Many2one(
        'hr.shift',
        string='Turno Día del Ciclo',
        domain="[('id', '!=', id)]",
    )
    cycle_night_shift_id = fields.Many2one(
        'hr.shift',
        string='Turno Noche del Ciclo',
        domain="[('id', '!=', id)]",
    )
    cycle_work_days = fields.Integer(string='Días Trabajo', default=2)
    cycle_rest_days = fields.Integer(string='Días Descanso', default=2)
    cycle_target_hours = fields.Float(
        string='Horas Objetivo del Ciclo',
        default=126.0,
        help='Horas promedio esperadas en el ciclo (ej. 126h cada 3 semanas)',
    )

    notes = fields.Text(string='Observaciones')

    @api.depends('hour_from', 'hour_to')
    def _compute_crosses_midnight(self):
        for rec in self:
            rec.crosses_midnight = rec.hour_to < rec.hour_from

    @api.depends('hour_from', 'hour_to', 'rest_time', 'crosses_midnight')
    def _compute_effective_hours(self):
        for rec in self:
            if rec.crosses_midnight:
                total = (24.0 - rec.hour_from) + rec.hour_to
            else:
                total = rec.hour_to - rec.hour_from
            rec.effective_hours = max(0.0, total - rec.rest_time)

    @api.constrains('code')
    def _check_unique_code(self):
        for rec in self:
            domain = [('code', '=', rec.code), ('id', '!=', rec.id), ('company_id', '=', rec.company_id.id)]
            if self.search(domain, limit=1):
                raise ValidationError('Ya existe un turno con el código "%s" en esta compañía.' % rec.code)

    @api.constrains('assignment_mode', 'weekday_line_ids')
    def _check_assignment_weekdays(self):
        for rec in self:
            if rec.assignment_mode == 'weekdays' and not rec.weekday_line_ids:
                raise ValidationError(
                    'Debe agregar al menos una línea de horario por día.'
                )

    def get_weekday_line(self, work_date):
        """Obtiene la línea de horario correspondiente a una fecha."""
        self.ensure_one()
        work_date = fields.Date.to_date(work_date)
        if self.assignment_mode != 'weekdays' or not work_date:
            return self.env['hr.shift.weekday.line']
        weekday = str(work_date.weekday())
        return self.weekday_line_ids.filtered(lambda line: line.weekday == weekday)[:1]

    def applies_on_date(self, work_date):
        """Indica si el turno puede asignarse en la fecha recibida."""
        self.ensure_one()
        if self.assignment_mode == 'all':
            return True
        return bool(self.get_weekday_line(work_date))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name)


class HrShiftWeekdayLine(models.Model):
    _name = 'hr.shift.weekday.line'
    _description = 'Horario del Turno por Día'
    _order = 'weekday'

    shift_id = fields.Many2one(
        'hr.shift',
        string='Turno',
        required=True,
        ondelete='cascade',
        index=True,
    )
    weekday = fields.Selection(
        WEEKDAY_SELECTION,
        string='Día',
        required=True,
    )
    hour_from = fields.Float(
        string='Hora Inicio',
        required=True,
        default=8.0,
    )
    hour_to = fields.Float(
        string='Hora Fin',
        required=True,
        default=17.0,
    )
    skip_rest_time = fields.Boolean(
        string='Omitir Descanso',
        default=False,
        help='Si está marcado, no descuenta el tiempo de descanso general '
             'al calcular las horas efectivas de este día.',
    )
    crosses_midnight = fields.Boolean(
        string='Cruza Medianoche',
        compute='_compute_hours',
        store=True,
    )
    effective_hours = fields.Float(
        string='Horas Efectivas',
        compute='_compute_hours',
        store=True,
    )

    _weekday_unique_per_shift = models.Constraint('unique(shift_id, weekday)', 'Solo puede existir una línea por día para cada turno.')

    @api.depends('hour_from', 'hour_to', 'skip_rest_time', 'shift_id.rest_time')
    def _compute_hours(self):
        for rec in self:
            rec.crosses_midnight = rec.hour_to < rec.hour_from
            if rec.crosses_midnight:
                total = (24.0 - rec.hour_from) + rec.hour_to
            else:
                total = rec.hour_to - rec.hour_from
            rest_time = 0.0 if rec.skip_rest_time else rec.shift_id.rest_time
            rec.effective_hours = max(0.0, total - rest_time)

    @api.constrains('hour_from', 'hour_to')
    def _check_hour_range(self):
        for rec in self:
            if not 0.0 <= rec.hour_from < 24.0 or not 0.0 <= rec.hour_to < 24.0:
                raise ValidationError('Las horas deben estar entre 00:00 y 23:59.')
