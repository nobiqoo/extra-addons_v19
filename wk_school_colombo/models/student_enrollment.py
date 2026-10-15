# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import str2bool
from odoo.tools.translate import code_translations

from .res_config_settings import ALLOW_MULTIPLE_ENROLLMENTS_PARAM

ACADEMIC_RESULT_SELECTION = [
    ('pending', 'Pendiente'),
    ('approved', 'Aprobado'),
    ('failed', 'No aprobado'),
]


class StudentEnrollment(models.Model):
    """Inscripcion del estudiante.

    Tarea 11292: el mensaje de inscripcion duplicada se arma con una f-string
    dentro de ``_()`` y por eso nunca llega traducido. Se delega la
    comprobacion en la validacion original de Webkul y solo se reemplaza el
    texto del error.

    Tarea 11293: cuando la institucion lo habilita, un estudiante puede tener
    varias inscripciones en curso al mismo tiempo, siempre que correspondan a
    niveles academicos distintos. Con el parametro desactivado no cambia nada.
    """

    _inherit = 'student.enrollment'

    # Requerimiento de campos académicos, sección "Libro en la inscripción" y
    # "Examen de clasificación".
    book_id = fields.Many2one('wk.books', string="Libro")
    has_classification_exam = fields.Boolean(string="¿Examen de clasificación?")
    classification_exam_result = fields.Char(
        string="Resultado examen de clasificación")

    # Histórico único de observaciones de la inscripción (pestaña
    # "Observaciones"): una sola tabla editable, sin importar el origen de
    # cada nota (inscripción, clase, facturación, administrativo o
    # comentario de la solicitud) -toda observación queda ligada a una
    # inscripción concreta, ver models/observation.py.
    observation_ids = fields.One2many(
        'wk.school.colombo.observation', 'enrollment_id', string="Observaciones")


    academic_result = fields.Selection(
        ACADEMIC_RESULT_SELECTION, string="Resultado académico",
        compute='_compute_academic_result', store=True)
    continuity_action = fields.Selection([
        ('promoted', 'Promovido'),
        ('finalized', 'Finalizado'),
    ], string="Acción de continuidad", copy=False)
    continuity_new_enrollment_id = fields.Many2one(
        'student.enrollment', string="Nueva inscripción",
        readonly=True, copy=False)
    finalization_date = fields.Date(
        string="Fecha de finalización", readonly=True, copy=False)
    finalization_user_id = fields.Many2one(
        'res.users', string="Usuario que finalizó", readonly=True, copy=False)

    @api.depends('student_subject_ids.scale_line_id.passes',
                 'student_subject_ids.consolidated_line_ids.result',
                 'student_subject_ids.consolidated_line_ids.consolidated_id.final_state')
    def _compute_academic_result(self):
        for enrollment in self:
            subjects = enrollment.student_subject_ids
            if not subjects:
                enrollment.academic_result = 'pending'
                continue
            statuses = [enrollment._wk_subject_academic_status(s) for s in subjects]
            if any(status is None for status in statuses):
                enrollment.academic_result = 'pending'
            elif all(statuses):
                enrollment.academic_result = 'approved'
            else:
                enrollment.academic_result = 'failed'

    def _wk_subject_academic_status(self, subject):
        """True aprueba, False reprueba, None pendiente, para una Materia.

        Requerimiento "Estructura de calificación avanzada" (2.9.4, 12.1):
        si la Materia pertenece a una Clase ofertada cuya estructura
        avanzada ya confirmó su corte Final (subtarea 8,
        models/grade_consolidated.py), se usa ese Pass/Fail. En cualquier
        otro caso se conserva el mecanismo estándar de la subtarea 6
        (scale_line_id.passes), sin cambios.
        """
        advanced_line = subject.consolidated_line_ids.filtered(
            lambda l: l.consolidated_id.final_state == 'confirmed')[:1]
        if advanced_line:
            if advanced_line.result == 'pending':
                return None
            return advanced_line.result == 'pass'
        if not subject.scale_line_id:
            return None
        return subject.scale_line_id.passes

    def get_student_subject(self):
        """Respeta "Visible en portal" para Materias con estructura
        avanzada confirmada (subtarea 8, requerimiento 2.10, 2.12).

        No cambia nada para Materias sin esa estructura. Para las que sí la
        tienen, una vez el corte Final está confirmado, la nota mostrada en
        el portal proviene siempre del Consolidado -nunca de
        scale_line_id.conversion_percent, que una estructura avanzada no
        usa- y se oculta (se muestra como sin nota, igual que una Materia
        que todavía no se ha calificado) mientras "Visible en portal" esté
        desmarcado para ese estudiante. No afecta la nota real, el
        Pass/Fail ni el histórico: solo lo que ve el estudiante.
        """
        grade_summary = super().get_student_subject()
        for entry in grade_summary:
            subject_row = self.student_subject_ids.filtered(
                lambda s: s.subject_id.id == entry['id'])[:1]
            line = subject_row.consolidated_line_ids.filtered(
                lambda l: l.consolidated_id.final_state == 'confirmed')[:1]
            if line:
                hidden = (
                    not line.portal_visible
                    or self.student_id.hide_grades_for_student
                    or line.consolidated_id.populate_class_id.hide_grades_for_class)
                entry['current_grade'] = 0 if hidden else line.final_grade
        return grade_summary

    def _wk_mark_continuity(self, action_type, execution_type, new_enrollment=False):
        """Marca esta inscripción de origen como Promovida o Finalizada y
        registra la trazabilidad (wk.school.colombo.enrollment.continuity.log,
        requerimiento 2.23-2.25). Reutilizado por create() (promoción
        individual), wizard/student_promote_wizard.py (finalización
        individual) y wizard/promote_bulk_wizard.py (masivo).
        """
        self.ensure_one()
        if action_type == 'promoted':
            self.continuity_action = 'promoted'
            self.continuity_new_enrollment_id = new_enrollment
            self.state = 'promote'
        else:
            self.continuity_action = 'finalized'
            self.finalization_date = fields.Date.context_today(self)
            self.finalization_user_id = self.env.user
        self.env['wk.school.colombo.enrollment.continuity.log'].create({
            'student_id': self.student_id.id,
            'origin_enrollment_id': self.id,
            'academic_result': self.academic_result,
            'origin_grade_id': self.grade_id.id,
            'new_grade_id': new_enrollment.grade_id.id if new_enrollment else False,
            'target_session_id': new_enrollment.session_id.id if new_enrollment else False,
            'target_academic_year_id': new_enrollment.academic_year_id.id if new_enrollment else False,
            'new_enrollment_id': new_enrollment.id if new_enrollment else False,
            'action_type': action_type,
            'execution_type': execution_type,
        })

    @api.model_create_multi
    def create(self, vals_list):
        enrollments = super().create(vals_list)
        for enrollment in enrollments:
            application = enrollment.application_form_id
            comment = application.application_comment
            if comment and not application.application_comment_converted:
                self.env['wk.school.colombo.observation'].create({
                    'enrollment_id': enrollment.id,
                    'origin': 'other',
                    'comment': comment,
                })
                application.application_comment_converted = True
        from_enrollment_id = self.env.context.get('from_enrollment_id')
        if self.env.context.get('promote') and from_enrollment_id:
            previous = self.browse(from_enrollment_id)
            for enrollment in enrollments:
                previous._wk_mark_continuity(
                    action_type='promoted', execution_type='individual',
                    new_enrollment=enrollment)
        return enrollments

    @api.onchange('grade_id', 'section_id')
    def _onchange_grade_default_book(self):
        """Propone el libro cuando todas las clases del nivel usan el mismo.

        La inscripción no se relaciona con una clase (wk.school.class) en
        particular -eso depende de las asignaturas que se agreguen despues-,
        así que se buscan las clases del mismo nivel/sección y solo se
        completa el libro cuando todas coinciden en el mismo; si hay varias
        clases con libros distintos o ninguna clase, se deja en blanco para
        que el usuario lo seleccione manualmente.
        """
        if not self.grade_id or self.book_id:
            return
        domain = [('grade_id', '=', self.grade_id.id)]
        if self.section_id:
            domain.append(('section_id', '=', self.section_id.id))
        books = self.env['wk.school.class'].search(domain).mapped('book_id')
        if len(books) == 1:
            self.book_id = books

    def _allow_multiple_active_enrollments(self):
        """Indica si están habilitadas las inscripciones activas simultáneas."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            ALLOW_MULTIPLE_ENROLLMENTS_PARAM, 'False')
        return str2bool(param, False)

    def _get_active_enrollment_in_grade(self):
        """Otra inscripción en curso del mismo estudiante y el mismo nivel."""
        self.ensure_one()
        return self.search([
            ('student_id', '=', self.student_id.id),
            ('grade_id', '=', self.grade_id.id),
            ('state', '=', 'progress'),
            ('id', '!=', self.id),
        ], limit=1)

    @api.constrains('student_id', 'grade_id')
    def check_for_unique_grade_enrollment(self):
        if self._allow_multiple_active_enrollments():
            # La duplicidad pasa a evaluarse solo entre inscripciones en curso:
            # las terminadas, canceladas o en borrador dejan de bloquear una
            # nueva inscripcion en el mismo nivel (p. ej. repetir un nivel ya
            # cursado). El bloqueo efectivo ocurre al confirmar.
            for enrollment in self:
                if enrollment.state != 'progress':
                    continue
                if enrollment._get_active_enrollment_in_grade():
                    raise ValidationError(self._duplicate_enrollment_message())
            return
        for enrollment in self:
            try:
                super(StudentEnrollment,
                      enrollment).check_for_unique_grade_enrollment()
            except ValidationError:
                raise ValidationError(_(
                    "An enrollment already exists for %(student)s in grade "
                    "%(grade)s.",
                    student=enrollment.student_id.name,
                    grade=enrollment.grade_id.name,
                )) from None

    @api.model
    def _duplicate_enrollment_message(self):
        return _("The student already has an active enrollment in this class.")

    @api.model
    def _unnumbered_enrollment_names(self):
        """Textos con los que nace una inscripción todavía sin numerar.

        El campo ``name`` de Webkul se crea con ``default=lambda self:
        _('New')``, así que el marcador queda guardado **ya traducido** al
        idioma del usuario que creó el registro ("Nuevo" en es_CO). Por eso se
        recogen las traducciones de ese msgid en todos los idiomas
        instalados, además del texto en inglés.

        El catálogo se pide explícitamente para ``wk_school_management``: la
        función ``_()`` resuelve el módulo a partir del archivo que la llama,
        de modo que invocarla aquí buscaría el msgid en el catálogo de
        wk_school_colombo y devolvería "New" sin traducir.
        """
        names = {'New'}
        for lang_code, _lang_name in self.env['res.lang'].get_installed():
            names.add(code_translations.get_python_translations(
                'wk_school_management', lang_code).get('New', 'New'))
        return names

    def _assign_enrollment_number(self):
        """Asigna el consecutivo a las inscripciones que aún no lo tienen.

        Corrige un defecto de Webkul que solo se ve en bases que no están en
        inglés: ``confirm_enrollment`` compara el nombre contra el literal
        ``'New'`` mientras el valor por omisión del campo es ``_('New')``. En
        español la comparación nunca acierta, la secuencia ``enrollment.form``
        no llega a consultarse y la inscripción se queda llamándose "Nuevo".

        El método es idempotente: cuando el nombre ya es un consecutivo -por
        ejemplo porque la base está en inglés y Webkul sí lo asignó- no se
        vuelve a pedir otro número.
        """
        unnumbered = self._unnumbered_enrollment_names()
        for enrollment in self:
            if enrollment.name and enrollment.name not in unnumbered:
                continue
            enrollment.name = self.env['ir.sequence'].next_by_code(
                'enrollment.form') or enrollment.name

    def confirm_enrollment(self):
        """Botón "Empezar ahora".

        Con el parámetro desactivado se delega íntegramente en Webkul. Con el
        parámetro activo se reimplementa el método
        (wk_school_management/models/student_enrollment.py, Webkul v5.0.4)
        cambiando únicamente el criterio de la validación: en lugar de bloquear
        por cualquier inscripción en curso del estudiante, se bloquea solo
        cuando ya existe una en curso del mismo nivel académico. El resto del
        flujo —cambio de estado y código QR— se conserva igual.

        En los dos caminos se numera la inscripción con
        ``_assign_enrollment_number``, porque el original solo lo consigue en
        bases en inglés. Se llama después de ``super()`` -que revienta si
        alguna inscripción no estaba en borrador- para no consumir números de
        la secuencia en una confirmación que no llegó a producirse.
        """
        if not self._allow_multiple_active_enrollments():
            result = super().confirm_enrollment()
            self._assign_enrollment_number()
            return result

        for obj in self:
            if obj.state != 'draft':
                raise UserError(_("Only new application can be marked as confirm."))

            if obj._get_active_enrollment_in_grade():
                raise UserError(obj._duplicate_enrollment_message())

            obj.write({'state': 'progress'})
            obj._assign_enrollment_number()
            obj.generate_qr_code()
        return True

    def _get_student_pricelist(self):
        """Lista de precios del contacto del estudiante (tarea 11293).

        ``property_product_pricelist`` ya resuelve la lista predeterminada de
        Odoo cuando el contacto no tiene una propia, así que no hace falta
        ningún respaldo adicional. Solo se lee: la inscripción nunca escribe
        sobre la lista del contacto.
        """
        self.ensure_one()
        partner = self.student_id.partner_id
        return partner.property_product_pricelist if partner \
            else self.env['product.pricelist']

    @api.onchange('fee_structure_id')
    def onchange_fee_structure_id(self):
        """Valora las líneas del resumen con la lista del estudiante.

        El original arma las líneas con la tarifa configurada en la estructura
        de tarifas. Aquí se les asigna la lista de precios del contacto y, si
        esa lista define un precio para el concepto de cobro, la tarifa se
        actualiza con ese valor.
        """
        res = super().onchange_fee_structure_id()
        pricelist = self._get_student_pricelist()
        for line in self.fee_summary_ids:
            line.pricelist_id = pricelist
            # La estructura se pasa explicitamente porque en el contexto del
            # onchange las lineas todavia no tienen resuelto enrollment_id.
            line._apply_pricelist_fee(self.fee_structure_id)
        return res

    def reset_enrollment(self):
        """Botón "Reiniciar".

        Al devolver una inscripción terminada a "En curso" Webkul aplica la
        misma restricción de una sola inscripción activa. Se condiciona con el
        mismo criterio que ``confirm_enrollment`` para que el parámetro no
        quede a medias; con el parámetro desactivado se delega en el original.
        """
        if not self._allow_multiple_active_enrollments():
            return super().reset_enrollment()

        for obj in self:
            if obj.state == 'complete':
                if obj._get_active_enrollment_in_grade():
                    raise ValidationError(obj._duplicate_enrollment_message())
                obj.state = 'progress'
            else:
                obj.state = 'draft'
        return True

    def promote_enrollment(self):
        for record in self:
            if record.continuity_action:
                raise UserError(_(
                    "La inscripción seleccionada ya fue procesada previamente."))
            if record.academic_result == 'failed':
                raise UserError(_(
                    "No se puede promover: %(student)s no aprobó el nivel "
                    "actual (%(grade)s). Revise el Resultado académico antes "
                    "de continuar.",
                    student=record.student_id.name, grade=record.grade_id.name))
            if record.academic_result == 'pending':
                raise UserError(_(
                    "No se puede promover: %(student)s todavía tiene "
                    "calificaciones pendientes en el nivel actual "
                    "(%(grade)s). Complete el proceso de evaluación antes de "
                    "continuar.",
                    student=record.student_id.name, grade=record.grade_id.name))
            if record.fee_status != 'fully':
                raise ValidationError(_(
                    "El estado del recibo de tarifas de %(student)s debe "
                    "estar completamente pagado antes de poder promoverlo.",
                    student=record.student_id.name))
        return super().promote_enrollment()

    def promote_bulk_enrollments(self):
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "Solo un usuario autorizado (Officer o Admin) puede promover "
                "o finalizar inscripciones."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Promover / Finalizar inscripciones"),
            'res_model': 'wk.school.colombo.promote.bulk.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_line_ids': [
                (0, 0, {'enrollment_id': enrollment.id}) for enrollment in self]},
        }
