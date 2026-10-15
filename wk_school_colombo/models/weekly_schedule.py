# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import ValidationError


class WeeklySchedule(models.Model):
    """Horario semanal de la clase ofertada (tarea 11292; ampliado por el
    requerimiento "Validación de cruces" -Asignatura/Docente/Salón/Horario-).

    El mensaje original de solape de ubicacion se construye con una f-string
    dentro de ``_()``, por lo que el texto llega ya interpolado al catalogo de
    traducciones y nunca coincide con ningun msgid: no se puede traducir desde
    un .po. Ademas muestra el valor tecnico del dia ("thursday") y el nombre
    almacenado de la franja ("02:00  PM-04:00  PM").

    Requerimiento de validación de cruces: se deja de delegar en ``super()``
    para la comparación en sí (aunque se conserva su mismo criterio de
    solape), porque esa validación de Webkul no excluye las Clases ofertadas
    inactivas de la comparación ni compara nunca por Docente -ambos son gaps
    reales que este requerimiento pide corregir/ampliar-.
    """

    _inherit = 'wk.weekly.schedule'

    def _get_weekday_label(self):
        """Etiqueta del dia en el idioma del usuario, en minuscula."""
        self.ensure_one()
        labels = dict(
            self._fields['weekday']._description_selection(self.env))
        return (labels.get(self.weekday) or self.weekday or '').lower()

    @api.model
    def _format_time_label(self, float_time):
        """Hora de 12 horas con el meridiano escrito en el idioma activo.

        No se reutiliza ``wk.class.timeslot.float_to_time`` porque devuelve el
        meridiano en ingles ("02:00  PM"), que es justamente lo que la tarea
        pide dejar de mostrar.
        """
        minutes = int(round((float_time or 0.0) * 60))
        hours, minutes = divmod(minutes, 60)
        meridian = _("AM") if hours < 12 else _("PM")
        return "%02d:%02d %s" % (hours % 12 or 12, minutes, meridian)

    @api.model
    def _wk_find_resource_conflicts(self, weekday, start_time, end_time,
                                     location_id=False, teacher_id=False,
                                     exclude_class_id=False):
        """wk.weekly.schedule de OTRAS Clases ofertadas ACTIVAS que se
        solapan en día+horario para el mismo Salón o el mismo Docente
        principal (no Docente asistente, fuera de alcance de este
        requerimiento). Se llama una vez por recurso para poder dar un
        mensaje distinto por tipo de cruce.

        El requerimiento define el cruce siempre entre DOS Clases ofertadas:
        ``exclude_class_id`` se pasa siempre que ya exista una Clase propia
        con la que comparar (ver _check_timeslot_overlap y
        populate_class.py::_check_teacher_overlap); el asistente de creación
        masiva, que compara contra clases que todavía no existen, lo omite.
        """
        domain = [
            ('weekday', '=', weekday),
            ('populate_class_id.is_active_class', '=', True),
        ]
        if exclude_class_id:
            domain.append(('populate_class_id', '!=', exclude_class_id))
        if location_id:
            domain.append(('location_id', '=', location_id))
        elif teacher_id:
            domain.append(('populate_class_id.teacher_id', '=', teacher_id))
        else:
            return self.browse()
        candidates = self.search(domain)
        return candidates.filtered(
            lambda c: start_time < c.timeslot_id.end_time
            and c.timeslot_id.start_time < end_time)

    @api.constrains('weekday', 'timeslot_id', 'location_id')
    def _check_timeslot_overlap(self):
        for record in self:
            timeslot = record.timeslot_id
            location_conflicts = record._wk_find_resource_conflicts(
                weekday=record.weekday,
                start_time=timeslot.start_time, end_time=timeslot.end_time,
                location_id=record.location_id.id,
                exclude_class_id=record.populate_class_id.id)
            if location_conflicts:
                other = location_conflicts[0]
                raise ValidationError(_(
                    "Cruce de Salón: el Salón %(location)s ya se encuentra "
                    "utilizado por otra Clase ofertada (%(other_class)s) el "
                    "%(weekday)s de %(start)s a %(end)s",
                    location=record.location_id.name,
                    other_class=other.populate_class_id.display_name.strip(),
                    weekday=record._get_weekday_label(),
                    start=self._format_time_label(timeslot.start_time),
                    end=self._format_time_label(timeslot.end_time),
                ))

            teacher = record.populate_class_id.teacher_id
            if teacher:
                teacher_conflicts = record._wk_find_resource_conflicts(
                    weekday=record.weekday,
                    start_time=timeslot.start_time, end_time=timeslot.end_time,
                    teacher_id=teacher.id,
                    exclude_class_id=record.populate_class_id.id)
                if teacher_conflicts:
                    other = teacher_conflicts[0]
                    raise ValidationError(_(
                        "Cruce de Docente: el docente %(teacher)s ya se "
                        "encuentra asignado a otra Clase ofertada "
                        "(%(other_class)s) el %(weekday)s de %(start)s a "
                        "%(end)s",
                        teacher=teacher.name,
                        other_class=other.populate_class_id.display_name.strip(),
                        weekday=record._get_weekday_label(),
                        start=self._format_time_label(timeslot.start_time),
                        end=self._format_time_label(timeslot.end_time),
                    ))
