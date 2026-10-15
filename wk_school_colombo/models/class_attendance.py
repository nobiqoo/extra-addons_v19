# -*- coding: utf-8 -*-
"""Horas de ausencia y observaciones de asistencia (subtarea 8, 2.11).

Desde "Marcar Asistencia" (wk.class.attendance.wizard, sobre las líneas
wk.student.class.attendance) se agrega el registro de Horas de ausencia -
total o parcial (llegada tarde)- y un campo de Observaciones de texto libre
del docente. El acumulado por estudiante y clase ofertada (ABS del
Consolidado de notas) se expone aquí como un método de utilidad
(_wk_total_absence_hours) para que la próxima fase de esta subtarea
(Consolidado) no tenga que volver a calcularlo.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StudentClassAttendance(models.Model):
    _inherit = 'wk.student.class.attendance'

    absence_hours = fields.Float(
        string="Horas de ausencia", default=0.0,
        help="Tiempo computable como ausencia del estudiante en esta "
             "sesión. Ausente toda la sesión: se sugieren las horas de "
             "duración de la clase (editable). Presente con una novedad de "
             "llegada tarde: se registra manualmente solo el tiempo de la "
             "demora -no es necesario marcarlo como Ausente para eso-. Sin "
             "ninguna novedad, queda en 0.")
    observations = fields.Text(
        string="Observaciones",
        help="Nota manual del docente sobre esta sesión. Queda en el "
             "histórico de asistencia del estudiante, junto a las horas de "
             "ausencia que la originaron.")

    @api.onchange('state')
    def _onchange_state_suggest_absence_hours(self):
        """Sugiere las horas de la sesión al marcar Ausente (2.11).

        Es solo una sugerencia editable -nunca sobreescribe un valor que el
        docente ya haya capturado a mano-, y nunca reduce automáticamente
        unas horas ya registradas al volver a marcar Presente (el docente
        decide si corresponde dejarlas en 0 o conservarlas, por ejemplo si
        hubo una llegada tarde antes del cambio de estado).
        """
        for record in self:
            if record.state == 'absent' and not record.absence_hours:
                record.absence_hours = record._wk_session_duration_hours()

    def _wk_session_duration_hours(self):
        """Duración en horas de la sesión (wk.class.timetable.timeslot_id).

        Devuelve 0.0 si la sesión no tiene franja horaria asignada -el
        docente registra las horas manualmente en ese caso-.
        """
        self.ensure_one()
        timeslot = self.class_id.timeslot_id
        if not timeslot:
            return 0.0
        return max(timeslot.end_time - timeslot.start_time, 0.0)

    @api.constrains('class_date', 'student_id', 'class_id')
    def _unique_attendance_date_wise(self):
        """Repite la validación de Webkul con un mensaje traducible.

        Reimplementa wk_school_management/models/class_attendance.py::
        _unique_attendance_date_wise (Webkul v5.0.4): el original arma el
        texto con un f-string ANTES de pasarlo a ``_()``
        (``_(f"... {record.student_id.name} ...")``), así que el msgid que
        llega a traducir es distinto en cada registro y nunca calza con
        ninguna entrada del catálogo -el mensaje queda siempre en inglés,
        sin importar el idioma del usuario-. Aquí se arma con un msgid fijo
        y los datos como parámetros de sustitución, que sí se puede traducir
        normalmente.
        """
        for record in self:
            attendance = self.search([
                ('class_date', '=', record.class_date),
                ('student_id', '=', record.student_id.id),
                ('class_id', '=', record.class_id.id),
                ('id', '!=', record.id)])

            if attendance:
                raise ValidationError(_(
                    "The attendance for %(student)s already exists for date "
                    "%(date)s in class %(class_name)s.",
                    student=record.student_id.name,
                    date=record.class_date,
                    class_name=record.class_id.name,
                ))

    @api.model
    def _wk_total_absence_hours(self, student, populate_class):
        """Acumulado de horas de ausencia de un estudiante en una clase.

        Usado por el Consolidado de notas (próxima fase de esta subtarea)
        para alimentar el campo ABS sin que el usuario administrativo tenga
        que volver a registrar el total manualmente (requerimiento 2.11).
        """
        lines = self.search([
            ('student_id', '=', student.id),
            ('class_id.populate_class_id', '=', populate_class.id),
        ])
        return sum(lines.mapped('absence_hours'))
