# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, time as dt_time


class HrOvertimeRule(models.Model):
    """Regla que mapea un rango horario y tipo de día a una categoría de hora extra de nómina CO.

    Permite configurar:
    - Desde qué hora hasta qué hora aplica la regla (soporta rangos que cruzan medianoche).
    - Si aplica en días normales o en festivos/domingos.
    - Si aplica a horas extras (después del turno) o a recargo nocturno (dentro del turno).
    - A qué categoría de hr.overtime.type de nómina corresponde.

    El sistema evalúa estas reglas en orden de ``sequence`` para determinar
    automáticamente qué categoría de hora extra asignar en cada novedad de asistencia.
    """
    _name = 'hr.overtime.rule'
    _description = 'Regla de Categorización de Hora Extra'
    _order = 'sequence, id'

    name = fields.Char(string='Nombre', required=True)

    overtime_type_id = fields.Many2one(
        'hr.overtime.type',
        string='Categoría H.E. (Nómina CO)',
        required=True,
        help='Tipo de hora extra de Nómina CO que aplica cuando se cumple esta regla.',
    )
    overtime_type_code = fields.Char(
        related='overtime_type_id.code',
        string='Código',
        store=False,
    )

    novelty_type = fields.Selection(
        selection=[
            ('extra_hours', 'Horas Extras (Genérico)'),
            ('extra_day_hours', 'H.E. Diurnas (HED)'),
            ('extra_night_hours', 'H.E. Nocturnas (HEN)'),
            ('night_surcharge', 'Recargo Nocturno (RN)'),
            ('compensatory', 'Festivo / Dominical (HEDF)'),
        ],
        string='Tipo de Novedad',
        required=True,
        default='extra_hours',
        help='Tipo de novedad de asistencia que se genera cuando aplica esta regla.\n'
             'Determina la categoría de la novedad en Control de Asistencia.',
    )

    apply_on = fields.Selection(
        selection=[
            ('normal', 'Día Normal (Lun – Sáb sin festivo)'),
            ('holiday_sunday', 'Festivo / Dominical'),
        ],
        string='Aplica en',
        required=True,
        default='normal',
        help='Día Normal: lunes a sábado sin festivo.\n'
             'Festivo / Dominical: domingos y días festivos del calendario.',
    )

    is_overtime = fields.Boolean(
        string='Solo Horas Extras',
        default=True,
        help='Activo → aplica únicamente a horas trabajadas DESPUÉS del turno (horas extras).\n'
             'Inactivo → aplica a horas DENTRO del turno (p. ej. recargo nocturno).',
    )

    hour_from = fields.Float(
        string='Desde (hora)',
        default=6.0,
        help='Inicio del rango horario (0 – 24). Ejemplos: 6.0 = 6:00 a.m.; 19.5 = 7:30 p.m.',
    )
    hour_to = fields.Float(
        string='Hasta (hora)',
        default=19.0,
        help='Fin del rango horario (0 – 24).\n'
             'Si es menor que "Desde", el rango cruza la medianoche (ej. 19 → 6 cubre 7pm-6am).',
    )

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )

    # ── Validaciones ──────────────────────────────────────────────────────────

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for rec in self:
            if not (0.0 <= rec.hour_from <= 24.0):
                raise ValidationError(
                    'La hora de inicio debe estar entre 0 y 24 en la regla "%s".' % rec.name)
            if not (0.0 <= rec.hour_to <= 24.0):
                raise ValidationError(
                    'La hora de fin debe estar entre 0 y 24 en la regla "%s".' % rec.name)
            if rec.hour_from == rec.hour_to:
                raise ValidationError(
                    'Las horas "Desde" y "Hasta" no pueden ser iguales en la regla "%s".' % rec.name)

    # ── Cómputo de traslape ───────────────────────────────────────────────────

    def _compute_overlap_hours(self, chunk_start, chunk_end):
        """Calcula las horas de traslape entre [chunk_start, chunk_end] y la ventana
        horaria definida en esta regla.

        chunk_start y chunk_end deben ser tz-aware datetimes en la misma zona horaria
        y dentro del mismo día calendario (la función _compute_hours_by_rules trocea
        el intervalo por día antes de llamar a este método).

        Devuelve un float con las horas de traslape (>= 0).
        """
        self.ensure_one()
        d = chunk_start.date()
        tz = chunk_start.tzinfo

        def to_dt(h):
            """Convierte float de hora a datetime tz-aware en el día d."""
            if h >= 24.0:
                base = datetime.combine(d + timedelta(days=1), dt_time(0, 0))
            else:
                total_min = int(round(h * 60))
                hh = total_min // 60
                mm = total_min % 60
                base = datetime.combine(d, dt_time(hh, mm))
            return tz.localize(base) if hasattr(tz, 'localize') else base.replace(tzinfo=tz)

        h_from = self.hour_from
        h_to = self.hour_to

        if h_from < h_to:
            # Rango normal (no cruza medianoche): [h_from, h_to)
            ws = max(chunk_start, to_dt(h_from))
            we = min(chunk_end, to_dt(h_to))
            return max(0.0, (we - ws).total_seconds() / 3600.0) if we > ws else 0.0
        else:
            # Rango que cruza medianoche: [h_from, 24:00) ∪ [00:00, h_to)
            midnight = to_dt(24.0)
            day_start = to_dt(0.0)

            # Parte 1: [h_from, midnight)
            ws1 = max(chunk_start, to_dt(h_from))
            we1 = min(chunk_end, midnight)
            h1 = max(0.0, (we1 - ws1).total_seconds() / 3600.0) if we1 > ws1 else 0.0

            # Parte 2: [00:00, h_to)
            ws2 = max(chunk_start, day_start)
            we2 = min(chunk_end, to_dt(h_to))
            h2 = max(0.0, (we2 - ws2).total_seconds() / 3600.0) if we2 > ws2 else 0.0

            return h1 + h2
