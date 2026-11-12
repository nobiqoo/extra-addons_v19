# -*- coding: utf-8 -*-
import base64
import io
import itertools

import xlsxwriter

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import str2bool

from .res_config_settings import ALLOW_SAME_DAY_PARAM


class PopulateClass(models.Model):
    _inherit = 'wk.school.class'

    # Requerimiento de campos académicos, sección "Clases Ofertadas": campo
    # de activación/inactivación independiente del ciclo de vida (state), y
    # libro estándar asignado a la clase (ver el onchange de la inscripción en
    # models/student_enrollment.py que lo propone como valor por defecto).
    # Sin lógica asociada: la subtarea de activación/inactivación es la que
    # define qué implica desactivar una clase.
    is_active_class = fields.Boolean(string="Clase activa", default=True)
    # Helper para la pestaña Observaciones (views/populate_class_view.xml):
    # student_ids es M2M a wk.student.subjects (Materias/matrículas), no a
    # student.student directamente -no se puede filtrar pick_student_id por
    # "('id', 'in', parent.student_ids...)" sin este paso intermedio. Antes
    # se usaba 'current_grade_id' (Nivel académico actual del estudiante),
    # que no identifica la Clase: mostraba TODOS los estudiantes de ese
    # Nivel (en otras clases del mismo Nivel) o NINGUNO si el Nivel no
    # coincidía exactamente, en vez de solo los matriculados en esta clase.
    enrolled_student_ids = fields.Many2many(
        'student.student', string="Estudiantes matriculados en esta clase",
        compute='_compute_enrolled_student_ids')

    @api.depends('student_ids.student_id')
    def _compute_enrolled_student_ids(self):
        for klass in self:
            klass.enrolled_student_ids = klass.student_ids.student_id
    # Ronda de ajustes post-prueba: catálogo configurable (models/sede.py)
    # en vez de company_id.
    sede_id = fields.Many2one('wk.school.colombo.sede', string="Sede")
    # Ronda de ajustes post-prueba: el catálogo bibliotecario de Webkul
    # (wk.books) no lo usa la institución y nunca trae resultados. Se pasa a
    # product.product, filtrado por el Boolean "¿Es libro?"
    # (models/product_product.py) para no traer certificados, exámenes y
    # demás productos de venta.
    book_id = fields.Many2one(
        'product.product', string="Libro",
        domain="[('is_book_element', '=', True)]")

    # Ajustes nov-2026: la materia solo se ofrece si esta ligada a la sede y a
    # la modalidad de la clase (models/grade_subject.py: sede_ids/modality_ids).
    subject_id = fields.Many2one(
        'wk.grade.subjects', string='Subject',
        domain="[('grade_id', '=', grade_id), ('is_active_subject', '=', True),"
               " ('sede_ids', 'in', sede_id), ('modality_ids', 'in', modality_id)]")

    # Ronda de ajustes post-prueba: catálogo configurable
    # (models/class_modality.py) en vez de un Selection fijo en código.
    modality_id = fields.Many2one(
        'wk.school.colombo.class.modality', string="Modalidad")

    @api.onchange('sede_id', 'modality_id')
    def _onchange_sede_modality_clear_subject(self):
        """Limpia la materia si ya no corresponde a la sede/modalidad."""
        subject = self.subject_id
        if subject and (
                (self.sede_id and self.sede_id not in subject.sede_ids)
                or (self.modality_id
                    and self.modality_id not in subject.modality_ids)):
            self.subject_id = False

    # Tarea 12439 (Reporte de Registros / Cursos): "Programa" de la clase
    # (ej. "Inglés Intermedio para Adultos"), necesario para el encabezado
    # del reporte y como filtro propio. No existía ninguna forma de
    # resolverlo para una clase cualquiera -la única relación previa,
    # grading_scale_id.program_type_id, solo aplica a las clases con
    # Estructura de calificación avanzada aplicada-. Campo independiente y
    # editable en cualquier clase; el onchange de abajo solo sugiere el
    # valor cuando la clase sí tiene esa Escala, sin forzarlo ni sobre
    # escribir una selección manual ya hecha.
    program_type_id = fields.Many2one(
        'wk.school.colombo.program.type', string="Programa")

    @api.onchange('grading_scale_id')
    def _onchange_grading_scale_suggest_program(self):
        if self.grading_scale_id.program_type_id and not self.program_type_id:
            self.program_type_id = self.grading_scale_id.program_type_id

    # Ronda de ajustes post-prueba: marca la única Clase ofertada que
    # representa el examen de clasificación (ver README 14.12 y
    # models/grade_consolidated.py::_wk_sync_classification_exam_result).
    # Sin esta marca explícita, ningún Consolidado puede escribir en
    # student.enrollment.classification_exam_result.
    is_classification_exam_class = fields.Boolean(
        string="Examen de clasificación",
        help="Marca esta Clase ofertada como el examen de clasificación: el "
             "comentario que el calificador escriba en el Consolidado se "
             "copia automáticamente al campo \"Resultado examen de "
             "clasificación\" de la Inscripción del estudiante. Ninguna otra "
             "Clase puede escribir ahí.")

    # Placeholder de visibilidad grupal de calificaciones, sin lógica
    # asociada (ver models/student_student.py::hide_grades_for_student).
    hide_grades_for_class = fields.Boolean(
        string="Ocultar calificaciones del grupo")

    # Requerimiento "Estructura de calificación avanzada" (2.6): Escala de
    # calificación con estructura avanzada aplicada a esta clase. El domain
    # solo ofrece escalas avanzadas y activas; una escala estándar (o una
    # avanzada inactiva) no puede seleccionarse aquí.
    grading_scale_id = fields.Many2one(
        'wk.grade.scales', string="Escala de calificación (avanzada)",
        domain="[('advanced_structure', '=', True), ('advanced_active', '=', True)]",
        help="Al aplicarla (botón \"Aplicar estructura de calificación\"), "
             "sus Componentes, cortes y ponderaciones se copian a la "
             "pestaña \"Tipos de actividad\" y quedan disponibles para el "
             "asistente \"Asignar tarea\". Mientras esta Escala esté "
             "seleccionada, las ponderaciones de la clase provienen "
             "siempre de ella y no se definen de forma independiente.")
    grading_cuts_count = fields.Selection(
        related='grading_scale_id.cuts_count', string="Número de cortes (Escala)")

    # Observaciones "realizadas durante la clase": el docente elige a qué
    # estudiante matriculado corresponde la nota.
    observation_ids = fields.One2many(
        'wk.school.colombo.observation', 'school_class_id', string="Observaciones")

    # store=True: estos campos se usan en el dominio de búsqueda de "Clases
    # ofertadas" (filter_domain del campo name, views/populate_class_view.xml)
    # y Odoo necesita poder convertir ese dominio a SQL al recalcular el panel
    # de filtros lateral (company_id/subject_id/grade_id); un campo calculado
    # no-almacenado revienta ahí con
    # "Cannot convert ... to SQL because it is not stored".
    weekly_schedule_summary = fields.Char(
        string="Horario", compute='_compute_weekly_schedule_summary', store=True)
    location_summary = fields.Char(
        string="Salón", compute='_compute_weekly_schedule_summary', store=True)

    @api.depends('weekly_schedule_ids.weekday', 'weekly_schedule_ids.timeslot_id',
                 'weekly_schedule_ids.location_id')
    def _compute_weekly_schedule_summary(self):
        for populate_class in self:
            lines = populate_class.weekly_schedule_ids
            schedule_parts = []
            for line in lines:
                if not (line.weekday and line.timeslot_id):
                    continue
                timeslot = line.timeslot_id
                schedule_parts.append("%s %s-%s" % (
                    line._get_weekday_label(),
                    line._format_time_label(timeslot.start_time),
                    line._format_time_label(timeslot.end_time),
                ))
            populate_class.weekly_schedule_summary = (
                ', '.join(schedule_parts) or False)
            locations = lines.mapped('location_id.name')
            populate_class.location_summary = (
                ', '.join(dict.fromkeys(locations)) or False)

    has_evaluation_activities = fields.Boolean(
        string="¿Tiene actividades de evaluación?",
        default=True,
        copy=True,
        help="Si está activo, la clase sigue el flujo estándar de evaluación: "
             "los tipos de actividad deben sumar el 100 % de la ponderación y "
             "no se puede marcar como hecha mientras queden actividades sin "
             "asignar.\n"
             "Si está inactivo, la clase se gestiona solo con sesiones y "
             "asistencia: no se exigen tipos de actividad, ponderaciones, "
             "entregas ni calificaciones (seminarios, inducciones, charlas y "
             "capacitaciones). El valor se define al crear la clase y después "
             "no puede cambiarse.")

    def write(self, vals):
        """Impide cambiar el tipo de gestión de una clase ya creada.

        La vista deja el campo en solo lectura después de guardar; esta
        validación cubre además las escrituras por importación, acciones de
        servidor o llamadas desde código. Cambiarlo con estudiantes, sesiones,
        actividades o calificaciones asociadas dejaría la clase inconsistente.
        """
        if 'has_evaluation_activities' in vals:
            changed = self.filtered(
                lambda c: c.has_evaluation_activities
                != vals['has_evaluation_activities'])
            if changed:
                raise UserError(_(
                    "The evaluation setting of a class cannot be changed once "
                    "the class has been created."))

        recompute_students = self.env['student.student']
        if 'student_ids' in vals or 'is_active_class' in vals:
            recompute_students = self.mapped('student_ids.student_id')

        res = super().write(vals)

        if 'student_ids' in vals or 'is_active_class' in vals:
            recompute_students |= self.mapped('student_ids.student_id')
            recompute_students._wk_recompute_academic_status(related_class=self[:1])

        # Requerimiento 2.6: con una estructura avanzada aplicada, las
        # ponderaciones provienen siempre de la Escala -el reparto
        # equitativo estándar no aplica-.
        if vals.get('grading_scale_id'):
            self.filtered(
                lambda c: c.grading_scale_id and c.divide_assignment_weightage
            ).write({'divide_assignment_weightage': False})
        return res

    @api.constrains('class_assignment_type_ids')
    def _check_for_type_weightage(self):
        """Omite la validación estándar en clases sin evaluación o avanzadas.

        Las clases con Escala de calificación avanzada (grading_scale_id)
        validan la suma de ponderaciones por corte en
        _check_advanced_weight_sum, no con esta validación estándar (que
        exige un único total de 100% sobre todos los tipos).
        """
        super(PopulateClass, self.filtered(
            lambda c: c.has_evaluation_activities and not c.grading_scale_id
        ))._check_for_type_weightage()

    @api.constrains('class_assignment_type_ids', 'grading_scale_id')
    def _check_advanced_weight_sum(self):
        """Valida la suma de ponderaciones por corte (2.3, 2.6).

        Espeja la validación de wk.grade.scales._check_component_weight_sum
        (models/grade_scale_structure.py) pero sobre las filas ya copiadas
        a la clase (wk.class.assignment.type), que son las que de verdad se
        usan en el cálculo -un cambio posterior en la Escala no las
        modifica automáticamente, ver action_apply_grading_structure-.
        """
        for record in self:
            if not record.grading_scale_id:
                continue
            lines = record.class_assignment_type_ids
            if not lines:
                continue
            scale = record.grading_scale_id
            if scale.cuts_count == '1':
                total = sum(lines.mapped('weightage'))
                if abs(total - 100.0) > 0.01:
                    raise ValidationError(_(
                        "La suma de las ponderaciones de \"%(klass)s\" es "
                        "%(total).2f%%; debe ser exactamente 100%%."
                    ) % {'klass': record.display_name, 'total': total})
            else:
                for cut_label, field_name in (
                        ("Midterm", 'weightage'), ("Final", 'weight_final')):
                    in_cut = lines.filtered(lambda t: t[field_name] > 0)
                    if not in_cut:
                        continue
                    total = sum(in_cut.mapped(field_name))
                    if abs(total - 100.0) > 0.01:
                        raise ValidationError(_(
                            "La suma de las ponderaciones de %(cut)s en "
                            "\"%(klass)s\" es %(total).2f%%; debe ser "
                            "exactamente 100%%."
                        ) % {'cut': cut_label, 'klass': record.display_name,
                             'total': total})

    def action_apply_grading_structure(self):
        """Copia los Componentes de la Escala a "Tipos de actividad" (2.6).

        Bloquea el reemplazo si ya existen calificaciones registradas para
        esta clase (requerimiento 2.6, último punto): evita dejar
        actividades y notas existentes huérfanas de su Componente de
        origen o con una ponderación que ya no corresponde.
        """
        self.ensure_one()
        if not self.grading_scale_id:
            raise UserError(_(
                "Seleccione primero una Escala de calificación avanzada."))

        already_applied = self.class_assignment_type_ids.filtered('component_id')
        if already_applied:
            graded = self.env['wk.class.assignment'].search(
                [('class_id', '=', self.id)]
            ).student_assignment_ids.filtered(
                lambda sa: sa.state != 'new' or sa.marks_obtained
                or sa.cp_line_ids)
            if graded:
                raise UserError(_(
                    "No se puede reemplazar la estructura de calificación: "
                    "ya existen calificaciones registradas para esta clase."))
            already_applied.unlink()

        lines = [
            (0, 0, {
                'assignment_type_id': component.assignment_type_id.id,
                'weightage': component.weight,
                'weight_final': component.weight_final,
                'component_id': component.id,
            })
            for component in self.grading_scale_id.component_ids.filtered('active')
        ]
        self.write({
            'class_assignment_type_ids': lines,
            'divide_assignment_weightage': False,
        })
        self._wk_get_or_create_consolidated().action_refresh()

    def action_open_consolidated(self):
        """Botón "Consolidado" de la clase: abre (o crea) su registro.

        Sin esto, la única manera de llegar al Consolidado de una clase es
        el menú "Maestros > Consolidado de notas", cuya lista no muestra el
        nombre de la clase (solo Módulo/Nivel/Docente/Periodo) -con varias
        clases del mismo Módulo y Nivel, como las de prueba de esta
        subtarea, son indistinguibles ahí-.
        """
        self.ensure_one()
        consolidated = self._wk_get_or_create_consolidated()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Consolidado de notas"),
            'res_model': 'wk.school.colombo.grade.consolidated',
            'view_mode': 'form',
            'res_id': consolidated.id,
        }

    def _wk_get_or_create_consolidated(self):
        """Alta del Consolidado de notas al aplicar la estructura (2.9).

        Un Consolidado por clase, creado la primera vez que se aplica una
        estructura avanzada; en una reaplicación (sin calificaciones
        previas, ver action_apply_grading_structure) se reutiliza el mismo
        registro en vez de duplicarlo.
        """
        self.ensure_one()
        Consolidated = self.env['wk.school.colombo.grade.consolidated']
        consolidated = Consolidated.search(
            [('populate_class_id', '=', self.id)], limit=1)
        return consolidated or Consolidated.create(
            {'populate_class_id': self.id})

    def confirm_class(self):
        """Confirma la clase sin exigir tipos de actividad cuando no evalúa.

        Reimplementa wk_school_management/models/populate_class.py::confirm_class
        (Webkul v5.0.4): se conservan la validación de estado y las de
        ponderación. Las clases con Escala avanzada validan por corte
        (_check_advanced_weight_sum); las demás, solo si sí evalúan.
        """
        for obj in self:
            if obj.state != 'new':
                raise UserError(
                    _("Classes only in new stage are allowed to be started."))

            if obj.grading_scale_id:
                if not obj.class_assignment_type_ids:
                    raise UserError(_(
                        "Aplique primero la estructura de calificación "
                        "(botón \"Aplicar estructura de calificación\")."))
                obj._check_advanced_weight_sum()
            elif obj.has_evaluation_activities:
                if not obj.class_assignment_type_ids:
                    raise UserError(
                        _("Add assignment types and their weightage."))

                total = sum(obj.class_assignment_type_ids.mapped('weightage'))
                if total != 100:
                    raise UserError(_(
                        "Please make sure to make assignment type weightage "
                        "sum to be 100%."))
            obj.state = 'confirm'
        return True

    def _allow_same_day_completion(self):
        """Indica si está habilitado el cierre el mismo día de finalización."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            ALLOW_SAME_DAY_PARAM, 'True')
        return str2bool(param, True)

    def assign_assignment(self):
        """Traduce el título del asistente y corrige el mensaje de plazo.

        Reimplementa wk_school_management/models/populate_class.py::assign_assignment
        (Webkul v5.0.4) completo, sin llamar a ``super()``, por dos motivos:

        - El original arma la acción con ``'name': 'Assign Class Assignment'``
          como literal, sin envolverlo en ``_()``, así que el título del
          diálogo no es traducible por catálogo (tarea 11155).
        - El catálogo ``es.po`` de Webkul trae mal traducido el mensaje de
          validación de plazo: "Assignment can only be assigned within the
          term." quedó como "La cesión sólo podrá realizarse dentro del
          plazo." ("cesión" = transferencia de derechos, no tiene relación;
          el término correcto es "tarea"). Ese mensaje se resuelve siempre
          contra el catálogo del módulo donde vive el ``_()`` que lo generó
          (odoo/tools/translate.py, ``CodeTranslations.get_python_translations``
          busca por módulo de origen vía inspección de la pila), así que no
          hay forma de sobreescribirlo desde el catálogo de este módulo: hay
          que reimplementar el método con el texto corregido.

        La validación de fechas es idéntica a la original. Se usa
        ``fields.Date.context_today`` en lugar de ``date.today()`` por el
        mismo motivo que en ``complete_class`` (comparar contra el día del
        usuario, no el del servidor en UTC).
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.start_date > today or self.end_date < today:
            raise ValidationError(
                _("The assignment can only be created within the term of the class."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Assign Class Assignment"),
            'res_model': 'wk.assignment.wizard',
            'views': [(self.env.ref('wk_school_management.assignment_wizard_form').id, 'form'), (False, "list"),],
            'target': 'new',
            'context': {
                'default_class_id': self.id,
                'default_grade_id': self.grade_id.id,
                'default_section_id': self.section_id.id,
                'default_subject_id': self.subject_id.id
            }
        }

    def complete_class(self):
        """Permite cerrar la clase el mismo día en que finaliza.

        Reimplementa wk_school_management/models/populate_class.py::complete_class
        (Webkul v5.0.4) cambiando únicamente la comparación de fechas. El
        original exige ``end_date < hoy``, por lo que obliga a esperar al día
        siguiente para cerrar cursos de corta duración (diplomados de un día,
        talleres, ciclos bimestrales). Con el parámetro activo el cierre se
        bloquea solo cuando ``end_date`` es posterior a hoy; al desactivarlo se
        vuelve a la validación estándar. El resto de validaciones y sus
        mensajes se conservan sin cambios.

        Se usa ``fields.Date.context_today`` en lugar de ``date.today()`` para
        comparar contra el día del usuario y no el del servidor en UTC.
        """
        self.ensure_one()
        assigned_types = set(self.env['wk.class.assignment'].search([
            ('class_id', '=', self.id)]).mapped('type_id.id'))
        required_types = set(self.class_assignment_type_ids.mapped('assignment_type_id.id'))

        missing_types = required_types - assigned_types
        if missing_types:
            missing_names = self.env['wk.assignment.type'].browse(list(missing_types)).mapped('name')
            raise ValidationError(
                _("All assignment types must be assigned before completing the class.\nMissing: %s") % ", ".join(missing_names)
            )
        if self.end_date:
            today = fields.Date.context_today(self)
            if self._allow_same_day_completion():
                blocked = self.end_date > today
            else:
                blocked = self.end_date >= today
            if blocked:
                raise ValidationError(_("Class can only be marked as completed once the duration of the class gets over."))
        self.state = 'complete'

    @api.constrains('teacher_id')
    def _check_teacher_overlap(self):
        for record in self:
            if not record.teacher_id:
                continue
            for line in record.weekly_schedule_ids:
                timeslot = line.timeslot_id
                conflicts = line._wk_find_resource_conflicts(
                    weekday=line.weekday,
                    start_time=timeslot.start_time, end_time=timeslot.end_time,
                    teacher_id=record.teacher_id.id,
                    exclude_class_id=record.id)
                if conflicts:
                    other = conflicts[0]
                    raise ValidationError(_(
                        "Cruce de Docente: el docente %(teacher)s ya se "
                        "encuentra asignado a otra Clase ofertada "
                        "(%(other_class)s) el %(weekday)s de %(start)s a "
                        "%(end)s",
                        teacher=record.teacher_id.name,
                        other_class=other.populate_class_id.display_name.strip(),
                        weekday=line._get_weekday_label(),
                        start=line._format_time_label(timeslot.start_time),
                        end=line._format_time_label(timeslot.end_time),
                    ))

    def action_bulk_activate(self):
        """Activa masivamente las Clases ofertadas seleccionadas en la lista.
        """
        for record in self:
            record.write({'is_active_class': True})

    def action_bulk_deactivate(self):
        """Inactiva masivamente las Clases ofertadas seleccionadas en la lista.
        """
        for record in self:
            record.write({'is_active_class': False})

    def action_generate_registration_report(self):
        """Botón "Generar Reporte de Registros / Cursos" (tarea 12439).

        Exporta a Excel las Clases ofertadas seleccionadas en la lista,
        agrupadas por Curso (Nivel académico) con subtotales y un total
        general, siguiendo la estructura del formato de referencia
        suministrado por el Colombo. Es de solo consulta/exportación: no
        modifica ningún registro.
        """
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "No tiene permisos para generar el Reporte de Registros / "
                "Cursos."))

        classes = self.sorted(key=lambda c: (c.grade_id.id, c.id))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Registros')
        bold = workbook.add_format({'bold': True})
        title_format = workbook.add_format({'bold': True, 'font_size': 12})

        programs = ', '.join(dict.fromkeys(
            classes.mapped('program_type_id.name'))) or _("Sin programa")
        sedes = ', '.join(dict.fromkeys(
            classes.mapped('sede_id.name'))) or _("Todas")
        start_dates = classes.filtered('start_date').mapped('start_date')
        end_dates = classes.filtered('end_date').mapped('end_date')
        date_range = (
            "%s / %s" % (min(start_dates), max(end_dates))
            if start_dates and end_dates else '')
        Schedule = self.env['wk.weekly.schedule']
        timeslots = classes.mapped('weekly_schedule_ids.timeslot_id')
        horario_range = (
            "%s - %s" % (
                Schedule._format_time_label(min(timeslots.mapped('start_time'))),
                Schedule._format_time_label(max(timeslots.mapped('end_time'))))
            if timeslots else '')
        generated_label = fields.Date.context_today(self).strftime('%Y-%m-%d')

        sheet.write(0, 0, _("REPORTE DE REGISTROS"), title_format)
        sheet.write(1, 0, "%s: %s" % (_("PROGRAMA"), programs))
        sheet.write(2, 0, "%s: %s" % (_("TIPO"), _("Reporte por cursos")))
        sheet.write(3, 0, "%s: %s" % (_("SEDE"), sedes))
        sheet.write(4, 0, "%s: %s" % (_("FECHA"), date_range))
        sheet.write(5, 0, "%s: %s" % (_("HORARIO"), horario_range))
        sheet.write(6, 0, "%s: %s" % (_("GENERADO"), generated_label))

        row = 8
        sheet.write(row, 0, "%s: %s" % (_("PROGRAMA"), programs), bold)
        row += 1

        headers = [
            _("No."), _("Curso"), _("Horario"), _("Fecha Ini"), _("Fecha Fin"),
            _("Profesor"), _("Assistant Teacher"), _("Libro"), _("Salón"),
            _("Cupos"), _("Inscritos"), _("Libres"),
        ]
        for col, label in enumerate(headers):
            sheet.write(row, col, label, bold)
        row += 1

        index = 0
        total_cupos = total_inscritos = 0
        for __, group_iter in itertools.groupby(
                classes, key=lambda c: c.grade_id.id):
            group = list(group_iter)
            grade_name = group[0].grade_id.name or ''
            group_cupos = group_inscritos = 0
            for klass in group:
                libres = klass.capacity - klass.total_enrolled
                sheet.write(row, 0, index)
                sheet.write(row, 1, grade_name)
                sheet.write(row, 2, klass.weekly_schedule_summary or '')
                sheet.write(row, 3, str(klass.start_date or ''))
                sheet.write(row, 4, str(klass.end_date or ''))
                sheet.write(row, 5, klass.teacher_id.name or '')
                sheet.write(row, 6, ', '.join(klass.teacher_ids.mapped('name')))
                sheet.write(row, 7, klass.book_id.name or '')
                sheet.write(row, 8, klass.location_summary or '')
                sheet.write(row, 9, klass.capacity)
                sheet.write(row, 10, klass.total_enrolled)
                sheet.write(row, 11, libres)
                row += 1
                index += 1
                group_cupos += klass.capacity
                group_inscritos += klass.total_enrolled

            sheet.write(row, 0, "%s %s" % (_("TOTAL CURSO"), grade_name), bold)
            sheet.write(row, 1, len(group), bold)
            sheet.write(row, 9, group_cupos, bold)
            sheet.write(row, 10, group_inscritos, bold)
            sheet.write(row, 11, group_cupos - group_inscritos, bold)
            row += 2
            total_cupos += group_cupos
            total_inscritos += group_inscritos

        sheet.write(row, 8, _("TOTAL"), bold)
        sheet.write(row, 9, total_cupos, bold)
        sheet.write(row, 10, total_inscritos, bold)
        sheet.write(row, 11, total_cupos - total_inscritos, bold)

        sheet.set_column(0, 0, 6)
        sheet.set_column(1, 1, 16)
        sheet.set_column(2, 2, 30)
        sheet.set_column(3, 4, 12)
        sheet.set_column(5, 6, 28)
        sheet.set_column(7, 8, 20)
        sheet.set_column(9, 11, 10)
        workbook.close()

        attachment = self.env['ir.attachment'].create({
            'name': 'Reporte_Registros_Cursos_%s.xlsx' % generated_label,
            'datas': base64.b64encode(output.getvalue()),
            'res_model': self._name,
            'res_id': classes[0].id,
            'mimetype': ('application/vnd.openxmlformats-officedocument'
                         '.spreadsheetml.sheet'),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def action_open_bulk_wizard(self):
        """Abre el asistente de creación masiva de Clases ofertadas."""
        return {
            'type': 'ir.actions.act_window',
            'name': _("Creación masiva de clases"),
            'res_model': 'wk.school.colombo.bulk.class.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
