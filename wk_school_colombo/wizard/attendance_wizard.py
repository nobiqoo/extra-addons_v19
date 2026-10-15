# -*- coding: utf-8 -*-
from odoo import models


class AttendanceWizard(models.TransientModel):
    _inherit = 'wk.attendance.wizard'

    def start_scheduled_class(self):
        """Corrige el estado inválido que "Comenzar" deja en cada estudiante.

        Reimplementa wk_school_management/wizard/attendance_wizard.py::
        start_scheduled_class (Webkul v5.0.4) completo, sin llamar a
        ``super()``: el original calcula el valor de ``state`` (Presente/
        Ausente, campo requerido de ``wk.student.class.attendance``) como
        ``entry_attendance.attendance_state if self.fetch_entry_attendance
        else False`` -si el usuario NO marca la casilla "¿Desea traer los
        registros de asistencia de entrada de los estudiantes?" (que queda
        sin marcar por defecto), el valor pasa a ser ``False`` para TODOS
        los estudiantes de la clase, lo que revienta el ``create()`` con
        "Falta el valor requerido para el campo 'Estado'" (NOT NULL) y
        cancela la transacción completa -ningún estudiante queda con
        asistencia creada y la clase tampoco pasa a "Corriendo"-.

        Se reemplaza ese ``False`` por ``'present'``: igual que al traer la
        asistencia de entrada, la fila queda creada con un valor válido que
        el docente corrige después desde "Marcar Asistencia" (los que
        realmente faltaron se cambian a Ausente ahí). El resto del método
        -incluida la creación de wk.student.attendance cuando no existe
        registro de entrada- se conserva sin cambios.
        """
        active_id = self.env.context.get('active_id')
        class_record = self.env['wk.class.timetable'].browse(active_id)

        class_record.write({'state': 'running'})

        students = class_record.student_ids
        for student in students:
            entry_attendance = self.env['wk.student.attendance'].search(
                [('student_id', '=', student.student_id.id),
                 ('attendance_date', '=', class_record.class_date)])
            if entry_attendance:
                values = {
                    'student_id': student.student_id.id,
                    'class_id': class_record.id,
                    'state': entry_attendance.attendance_state if self.fetch_entry_attendance else 'present',
                    'class_date': class_record.class_date,
                    'student_attendance_id': entry_attendance.id,
                }
                self.env['wk.student.class.attendance'].create(values)
            else:
                vals = {
                    'student_id': student.student_id.id,
                    'attendance_date': class_record.class_date,
                    'attendance_state': 'absent',
                }
                entry_attendance = self.env['wk.student.attendance'].create(vals)

                values = {
                    'student_id': student.student_id.id,
                    'class_id': class_record.id,
                    'state': entry_attendance.attendance_state if self.fetch_entry_attendance else 'present',
                    'class_date': class_record.class_date,
                    'student_attendance_id': entry_attendance.id,
                }
                self.env['wk.student.class.attendance'].create(values)
