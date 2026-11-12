# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WkSchoolColomboBulkClassWizard(models.TransientModel):
    """Creación masiva de Clases ofertadas.

    Requerimiento "Gestión de la vista lista de Clases ofertadas" (2.5-2.9):
    permite registrar datos generales comunes y varias líneas antes de
    confirmar, creando una Clase ofertada (``wk.school.class``) independiente
    por cada línea -ninguna línea se escribe hasta que el usuario confirma-.
    """

    _name = 'wk.school.colombo.bulk.class.wizard'
    _description = 'Creación masiva de Clases ofertadas'

    academic_year_id = fields.Many2one(
        'wk.academic.year', string="Programación académica", required=True)
    # Ronda de ajustes post-prueba: catálogo configurable
    # (models/class_modality.py) en vez de un Selection fijo.
    modality_id = fields.Many2one(
        'wk.school.colombo.class.modality', string="Modalidad", required=True)
    # Ronda de ajustes post-prueba: catálogo configurable (models/sede.py)
    # en vez de company_id -ya no se usa como "Sede" en la interfaz, pero
    # wk.school.class sigue exigiendo una Compañía real (campo estándar de
    # Odoo); se mantiene con su valor por defecto, sin pedírselo al usuario.
    sede_id = fields.Many2one(
        'wk.school.colombo.sede', string="Sede", required=True)
    company_id = fields.Many2one(
        'res.company', string="Compañía", required=True,
        default=lambda self: self.env.company)
    term_id = fields.Many2one(
        'wk.grade.terms', string="Periodo académico", required=True,
        domain="[('academic_year_id', '=', academic_year_id)]")
    line_ids = fields.One2many(
        'wk.school.colombo.bulk.class.line', 'wizard_id', string="Clases a crear")

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        if self.term_id and self.term_id.academic_year_id != self.academic_year_id:
            self.term_id = False

    @api.onchange('modality_id', 'sede_id')
    def _onchange_modality_sede(self):
        """Limpia Nivel/Módulo de las líneas que ya no corresponden.

        Ajustes nov-2026: los niveles y módulos se filtran por la modalidad y
        la sede elegidas (ligadas en la configuración del Nivel y de la
        Materia). Al cambiar alguna, las líneas con un Nivel o Módulo que no
        pertenece a la nueva combinación se vacían para forzar a elegir de
        nuevo.
        """
        for line in self.line_ids:
            grade = line.grade_id
            if grade and (
                    (self.modality_id and self.modality_id not in grade.modality_ids)
                    or (self.sede_id and self.sede_id not in grade.sede_ids)):
                line.grade_id = False
                line.subject_id = False
                continue
            subject = line.subject_id
            if subject and (
                    (self.modality_id and self.modality_id not in subject.modality_ids)
                    or (self.sede_id and self.sede_id not in subject.sede_ids)):
                line.subject_id = False

    def _wk_check_lines_modality_sede(self):
        """Mensajes de error para líneas cuyo Nivel/Módulo no corresponde a
        la modalidad y sede del asistente (revalidación al confirmar)."""
        self.ensure_one()
        errors = []
        for index, line in enumerate(self.line_ids, start=1):
            label = _("Línea %(index)s (%(grade)s)") % {
                'index': index, 'grade': line.grade_id.name or _("sin nivel")}
            if line.grade_id and (
                    self.modality_id not in line.grade_id.modality_ids
                    or self.sede_id not in line.grade_id.sede_ids):
                errors.append(_(
                    "%(label)s: el nivel no está configurado para la "
                    "modalidad y la sede seleccionadas.") % {'label': label})
            if line.subject_id and (
                    self.modality_id not in line.subject_id.modality_ids
                    or self.sede_id not in line.subject_id.sede_ids):
                errors.append(_(
                    "%(label)s: el módulo no está configurado para la "
                    "modalidad y la sede seleccionadas.") % {'label': label})
        return errors

    def action_create_classes(self):
        """Valida todas las líneas y, si no hay errores, crea las clases.

        Requerimiento 2.9: los errores deben poder corregirse antes de
        confirmar -no se crea ningún registro si alguna línea es inválida-,
        y el mensaje debe identificar qué línea presenta el problema.

        Requerimiento "Validación de cruces" (2.9): además de cupo/fechas, se
        valida que las líneas no se crucen en Docente/Salón entre sí ni
        contra Clases ofertadas ya existentes, antes de crear nada.
        """
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Agregue al menos una línea antes de crear las clases."))

        lines = list(enumerate(self.line_ids, start=1))
        labels = {
            index: _("Línea %(index)s (%(grade)s)") % {
                'index': index, 'grade': line.grade_id.name or _("sin nivel")}
            for index, line in lines}

        errors = self._wk_check_lines_modality_sede()
        for index, line in lines:
            label = labels[index]
            if line.capacity <= 0:
                errors.append(_("%(label)s: el cupo debe ser mayor a 0.") % {'label': label})
            if line.start_date and line.end_date and line.start_date > line.end_date:
                errors.append(_(
                    "%(label)s: la fecha de inicio no puede ser posterior a "
                    "la fecha de finalización.") % {'label': label})

        # Entre líneas del propio proceso (escenarios 11-12).
        WeeklySchedule = self.env['wk.weekly.schedule']
        for i, (index_a, line_a) in enumerate(lines):
            for index_b, line_b in lines[i + 1:]:
                if line_a.weekday != line_b.weekday:
                    continue
                if not (line_a.timeslot_id and line_b.timeslot_id):
                    continue
                overlap = (line_a.timeslot_id.start_time < line_b.timeslot_id.end_time
                           and line_b.timeslot_id.start_time < line_a.timeslot_id.end_time)
                if not overlap:
                    continue
                if line_a.teacher_id and line_a.teacher_id == line_b.teacher_id:
                    errors.append(_(
                        "%(label_a)s y %(label_b)s: mismo Docente "
                        "(%(teacher)s), mismo día y horario superpuesto.") % {
                        'label_a': labels[index_a], 'label_b': labels[index_b],
                        'teacher': line_a.teacher_id.name})
                if line_a.location_id and line_a.location_id == line_b.location_id:
                    errors.append(_(
                        "%(label_a)s y %(label_b)s: mismo Salón "
                        "(%(location)s), mismo día y horario superpuesto.") % {
                        'label_a': labels[index_a], 'label_b': labels[index_b],
                        'location': line_a.location_id.name})

        # Contra Clases ofertadas ya existentes (escenario 13).
        for index, line in lines:
            if not (line.weekday and line.timeslot_id):
                continue
            label = labels[index]
            start_time, end_time = line.timeslot_id.start_time, line.timeslot_id.end_time
            if line.location_id:
                conflicts = WeeklySchedule._wk_find_resource_conflicts(
                    weekday=line.weekday, start_time=start_time, end_time=end_time,
                    location_id=line.location_id.id)
                if conflicts:
                    other = conflicts[0]
                    errors.append(_(
                        "%(label)s: cruce de Salón (%(location)s) con la "
                        "Clase ofertada existente %(other_class)s, el "
                        "%(weekday)s de %(start)s a %(end)s") % {
                        'label': label, 'location': line.location_id.name,
                        'other_class': other.populate_class_id.display_name.strip(),
                        'weekday': other._get_weekday_label(),
                        'start': other._format_time_label(other.timeslot_id.start_time),
                        'end': other._format_time_label(other.timeslot_id.end_time)})
            if line.teacher_id:
                conflicts = WeeklySchedule._wk_find_resource_conflicts(
                    weekday=line.weekday, start_time=start_time, end_time=end_time,
                    teacher_id=line.teacher_id.id)
                if conflicts:
                    other = conflicts[0]
                    errors.append(_(
                        "%(label)s: cruce de Docente (%(teacher)s) con la "
                        "Clase ofertada existente %(other_class)s, el "
                        "%(weekday)s de %(start)s a %(end)s") % {
                        'label': label, 'teacher': line.teacher_id.name,
                        'other_class': other.populate_class_id.display_name.strip(),
                        'weekday': other._get_weekday_label(),
                        'start': other._format_time_label(other.timeslot_id.start_time),
                        'end': other._format_time_label(other.timeslot_id.end_time)})

        if errors:
            raise UserError("\n".join(errors))

        vals_list = []
        for line in self.line_ids:
            vals_list.append({
                # El Título es obligatorio a nivel de modelo (lo arma el
                # usuario a mano en el formulario individual, ver
                # wk_school_management/models/populate_class.py:28 y 119);
                # en el mockup de creación masiva no hay un campo aparte
                # para esto, así que se usa el Nivel de la línea, igual que
                # en los ejemplos del prototipo ("Sabatino A", "Sabatino B").
                'title': line.grade_id.name,
                'company_id': self.company_id.id,
                'sede_id': self.sede_id.id,
                'session_id': self.academic_year_id.session_id.id,
                'academic_year_id': self.academic_year_id.id,
                'term_id': self.term_id.id,
                'modality_id': self.modality_id.id,
                'grade_id': line.grade_id.id,
                'subject_id': line.subject_id.id,
                'teacher_id': line.teacher_id.id,
                'teacher_ids': [(6, 0, line.teacher_ids.ids)],
                'capacity': line.capacity,
                'start_date': line.start_date,
                'end_date': line.end_date,
                'book_id': line.book_id.id,
                'is_active_class': line.is_active_line,
            })
        classes = self.env['wk.school.class'].create(vals_list)

        # Requerimiento "Validación de cruces": el Horario semanal es la
        # fuente de verdad también para las clases creadas masivamente -se
        # crea la línea real por cada clase, no solo el dato de referencia-.
        # Esto también dispara, como red de seguridad, la validación de
        # wk.weekly.schedule._check_timeslot_overlap.
        for created_class, line in zip(classes, self.line_ids):
            self.env['wk.weekly.schedule'].create({
                'weekday': line.weekday,
                'timeslot_id': line.timeslot_id.id,
                'location_id': line.location_id.id,
                'populate_class_id': created_class.id,
            })

        # Ronda de ajustes post-prueba: el flujo individual permite aplicar
        # una Escala de calificación avanzada (botón "Aplicar estructura de
        # calificación", ver models/populate_class.py); el masivo no lo
        # ofrecía. Una escala por línea, porque cada línea puede ser un
        # Nivel/Módulo distinto que requiera una escala distinta.
        for created_class, line in zip(classes, self.line_ids):
            if line.grading_scale_id:
                created_class.grading_scale_id = line.grading_scale_id
                created_class.action_apply_grading_structure()

        return {
            'type': 'ir.actions.act_window',
            'name': _("Clases creadas"),
            'res_model': 'wk.school.class',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('wk_school_management.wk_school_class_tree').id, 'list'),
                (self.env.ref('wk_school_management.wk_school_class_form').id, 'form'),
            ],
            'domain': [('id', 'in', classes.ids)],
        }


class WkSchoolColomboBulkClassLine(models.TransientModel):
    """Una línea del asistente de creación masiva = una futura Clase ofertada."""

    _name = 'wk.school.colombo.bulk.class.line'
    _description = 'Línea de creación masiva de Clase ofertada'

    wizard_id = fields.Many2one(
        'wk.school.colombo.bulk.class.wizard', required=True, ondelete='cascade')
    grade_id = fields.Many2one('wk.school.grade', string="Nivel", required=True)
    subject_id = fields.Many2one(
        'wk.grade.subjects', string="Módulo", required=True,
        domain="[('grade_id', '=', grade_id), ('is_active_subject', '=', True)]")
    teacher_id = fields.Many2one(
        'hr.employee', string="Docente principal", required=True,
        domain="[('is_teacher', '=', True)]")
    teacher_ids = fields.Many2many(
        'hr.employee', string="Docente asistente",
        domain="[('is_teacher', '=', True)]")
    # Requerimiento "Validación de cruces" (2.9): para poder validar cruces
    # de verdad durante la creación masiva hace falta el día -Día, Horario y
    # Salón pasan de ser solo de referencia (Subtarea anterior) a ser
    # funcionales: al confirmar, se crea también la línea real de Horario
    # semanal de cada clase (ver action_create_classes)-.
    # Mismos valores que wk.weekly.schedule.DAYS, declarados aquí como lista
    # estática (no lambda): un Selection dinámico no genera los registros
    # ir.model.fields.selection que Odoo necesita para poder traducirlo.
    weekday = fields.Selection([
        ('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'), ('friday', 'Friday'), ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ], string="Día", required=True)
    timeslot_id = fields.Many2one('wk.class.timeslot', string="Horario", required=True)
    location_id = fields.Many2one('wk.class.location', string="Salón", required=True)
    capacity = fields.Integer(string="Cupo", required=True, default=1)
    start_date = fields.Date(string="Fecha de inicio", required=True)
    end_date = fields.Date(string="Fecha de finalización", required=True)
    # Ronda de ajustes post-prueba: mismo campo y domain que
    # wk.school.class.book_id (ver models/populate_class.py); el catálogo
    # bibliotecario de Webkul (wk.books) no lo usa la institución.
    book_id = fields.Many2one(
        'product.product', string="Libro",
        domain="[('is_book_element', '=', True)]")
    # Una Escala por línea (cada línea puede ser un Nivel/Módulo distinto),
    # mismo domain que wk.school.class.grading_scale_id: solo ofrece Escalas
    # con estructura avanzada activa, y se aplica automáticamente a la clase
    # creada (ver action_create_classes).
    grading_scale_id = fields.Many2one(
        'wk.grade.scales', string="Escala de calificación (avanzada)",
        domain="[('advanced_structure', '=', True), ('advanced_active', '=', True)]")
    is_active_line = fields.Boolean(string="Activa", default=True)

    @api.onchange('grade_id')
    def _onchange_grade_id(self):
        """Precarga las fechas desde el Periodo académico del asistente.

        Quedan editables por línea (igual que el campo real
        ``wk.school.class.start_date/end_date``, ``related`` del término
        pero ``readonly=False``): se usa como punto de partida, no como
        valor fijo.
        """
        for line in self:
            term = line.wizard_id.term_id
            if term and not line.start_date:
                line.start_date = term.start_date
            if term and not line.end_date:
                line.end_date = term.end_date
