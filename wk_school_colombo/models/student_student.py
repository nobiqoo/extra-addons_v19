# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

from .student_status_log import ACADEMIC_STATUS_SELECTION


class StudentStudent(models.Model):
    """Enlaza el estudiante con su contacto usando el documento de identidad.

    Tarea 11151: el estudiante no almacena tipo ni numero de identificacion
    (se reutilizan los del contacto relacionado); la informacion se toma de la
    solicitud que origino el registro.
    """

    _inherit = 'student.student'

    # Tarea 11152: la solicitud ya puede guardarse sin fotografia, y al
    # inscribir el asistente copia student_image de la solicitud al estudiante
    # (wk_school_management/wizard/enroll_wizard.py). Si el estudiante siguiera
    # exigiendola, la inscripcion de un aspirante sin foto fallaria; el campo
    # se completa despues, en el estudiante o en su contacto.
    student_image = fields.Image(required=False)

    # Espejo de los campos generales cargados en la solicitud (requerimiento
    # de campos académicos): se copian al inscribir (wizard/enroll_wizard.py)
    # para que la información quede disponible en la ficha del estudiante sin
    # tener que volver a diligenciarla.
    program_type_id = fields.Many2one(
        'wk.school.colombo.program.type', string="Tipo de programa")
    # No se redeclaran required=True aqui (a diferencia de wk.application.form):
    # el asistente de inscripcion (wk_school_management/wizard/enroll_wizard.py)
    # crea el estudiante con un INSERT que no incluye estos campos -los copia
    # este modulo despues, en wizard/enroll_wizard.py::_wk_copy_application_fields_to_student()-
    # y una restriccion NOT NULL en la base de datos rompe ese INSERT antes de
    # que la copia llegue a ejecutarse. Mismo criterio ya aplicado a
    # student_image (tarea 11152): la obligatoriedad real se exige en la
    # solicitud (wk.application.form), que es donde el usuario los diligencia.
    street = fields.Char()
    barrio = fields.Char(string="Barrio / corregimiento")
    city_id = fields.Many2one(
        'res.city', string="Ciudad o municipio",
        domain="[('state_id', '=?', state_id)]")
    issuance_city_id = fields.Many2one(
        'res.city', string="Municipio de expedición del documento")
    origin_city_id = fields.Many2one(
        'res.city', string="Municipio / lugar de origen")
    tipo_persona = fields.Selection([
        ('natural', 'Persona natural'),
        ('juridica', 'Persona jurídica'),
        ('natural_comerciante', 'Natural comerciante'),
        ('codigo_interno', 'Código interno'),
    ], string="Tipo de persona", default='natural')
    estado_civil = fields.Selection([
        ('soltero', 'Soltero(a)'),
        ('casado', 'Casado(a)'),
        ('union_libre', 'Unión libre'),
        ('divorciado', 'Divorciado(a)'),
        ('viudo', 'Viudo(a)'),
    ], string="Estado civil")
    nivel_formacion = fields.Selection([
        ('ninguno', 'Ninguno'),
        ('primaria', 'Primaria'),
        ('secundaria', 'Secundaria'),
        ('tecnico', 'Técnico'),
        ('tecnologo', 'Tecnólogo'),
        ('pregrado', 'Pregrado'),
        ('especializacion', 'Especialización'),
        ('maestria', 'Maestría'),
        ('doctorado', 'Doctorado'),
    ], string="Nivel de formación")
    idioma_nativo = fields.Selection([
        ('espanol', 'Español'),
        ('ingles', 'Inglés'),
        ('frances', 'Francés'),
        ('otro', 'Otro'),
    ], string="Idioma nativo", default='espanol')
    idioma_nativo_otro = fields.Char(string="¿Cuál idioma?")
    ocupacion_actual = fields.Selection([
        ('estudiante', 'Estudiante'),
        ('empleado', 'Empleado'),
        ('independiente', 'Independiente'),
        ('desempleado', 'Desempleado'),
        ('hogar', 'Hogar'),
        ('pensionado', 'Pensionado'),
        ('otro', 'Otro'),
    ], string="Ocupación actual")
    landline_phone = fields.Char(string="Teléfono fijo")
    additional_phone = fields.Char(string="Teléfono adicional")
    additional_mobile = fields.Char(string="Celular adicional")
    email_dian = fields.Char(
        string="Correo electrónico DIAN",
        help="Correo independiente del correo electrónico principal. Se usa "
             "para la Facturación Electrónica.")
    contact_preference = fields.Selection([
        ('mobile', 'Celular'),
        ('email', 'Correo electrónico'),
        ('landline', 'Teléfono fijo'),
    ], string="Preferencia de contacto")
    guardian_ids = fields.One2many(
        'wk.school.colombo.guardian', 'student_id', string="Acudientes")

    # Restricción del estudiante: visible solo para Officer/Admin (ver
    # groups= en la vista). El check va en el encabezado general; el motivo
    # se consulta desde la pestaña "Disciplina" según el criterio de
    # aceptación del requerimiento.
    is_restricted = fields.Boolean(
        string="Estudiante con restricción", tracking=True)
    restriction_reason = fields.Text(string="Motivo / observación de la restricción")

    age = fields.Integer(
        string="Edad", compute='_compute_age',
        help="Calculada a partir de la fecha de nacimiento.")

    # Placeholder de visibilidad de calificaciones: sin lógica asociada. La
    # lógica real de ocultar/mostrar calificaciones corresponde a la subtarea
    # de estructura de calificación.
    hide_grades_for_student = fields.Boolean(
        string="Ocultar calificaciones al estudiante")

    # Histórico agregado por estudiante: ambos modelos ya tienen student_id
    # como FK directo, así que un One2many simple reúne los registros de
    # todas las inscripciones sin necesitar un compute.
    discipline_ids = fields.One2many(
        'wk.student.discipline', 'student_id', string="Disciplina")
    observation_ids = fields.One2many(
        'wk.school.colombo.observation', 'student_id', string="Observaciones")
    academic_status = fields.Selection(
        ACADEMIC_STATUS_SELECTION, string="Estado académico",
        default='new', tracking=True, copy=False)
    status_log_ids = fields.One2many(
        'wk.school.colombo.student.status.log', 'student_id',
        string="Histórico de estados académicos")
    academic_result = fields.Selection(
        related='current_enrollment_id.academic_result',
        string="Resultado académico")

    @api.depends('dob')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for student in self:
            if not student.dob:
                student.age = 0
                continue
            dob = student.dob
            student.age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day))

    @api.depends('enrollment_ids.state', 'enrollment_ids.enrollment_date')
    def _compute_enrollment_grade_id(self):
        """Reimplementa wk_school_management/models/student_student.py
        (Webkul v5.0.4) para admitir varias inscripciones en curso.

        Tarea 11293: al habilitar las inscripciones activas simultaneas, el
        calculo original de Webkul revienta. Hace un search() de las
        inscripciones en estado 'progress' y asigna el resultado completo a
        current_enrollment_id, que es un Many2one; con una sola inscripcion
        activa siempre venia un unico registro, pero con dos el ORM lanza
        "ValueError: Wrong value for student.student.current_enrollment_id:
        student.enrollment(25, 23)" al recalcular, y la segunda inscripcion no
        se puede guardar.

        Aqui se toma una sola: la inscripcion en curso mas reciente por fecha
        de inscripcion (y, a igual fecha, la de id mayor). Los campos son
        Many2one y almacenados, y se muestran en la ficha del estudiante, en
        el portal y en el asistente de inscripcion, asi que tienen que apuntar
        a una sola matricula; "la mas reciente" es la que corresponde a la
        matricula actual del estudiante. No se ordena por write_date -el
        _order del modelo- porque cualquier edicion de una inscripcion vieja
        cambiaria cual figura como actual.

        Con el parametro desactivado el comportamiento es identico al
        original: solo puede haber una inscripcion en curso y es la que se
        elige. Se anade enrollment_date a las dependencias; en Odoo 19 las de
        la version heredada se fusionan con las del metodo original.
        """
        for student in self:
            enrollment = self.env['student.enrollment'].search(
                [('student_id', '=', student.id), ('state', '=', 'progress')],
                order='enrollment_date desc, id desc',
                limit=1,
            )
            student.current_enrollment_id = enrollment
            student.current_grade_id = enrollment.grade_id

    def _wk_find_partner_by_identification(self):
        """Contacto activo que coincide en tipo y numero de documento."""
        self.ensure_one()
        application = self.application_id
        if not application:
            return self.env['res.partner'].browse()
        matches = application._wk_find_identification_matches()
        return matches['partner'][:1]

    def _prepare_related_partner_vals(self):
        """Agrega al contacto los nombres separados y el documento.

        Extiende wk_school_management/models/student_student.py para que el
        contacto creado o actualizado desde el estudiante quede con los campos
        de la localizacion colombiana diligenciados (criterios 8, 13 y 18 de la
        tarea 11151). El origen de los datos es la solicitud de inscripcion.
        """
        vals = super()._prepare_related_partner_vals()
        application = self.application_id
        if not application:
            return vals
        identification_vals = {
            'name1': application.name1,
            'name2': application.name2,
            'lastname1': application.lastname1,
            'lastname2': application.lastname2,
            'l10n_latam_identification_type_id':
                application.l10n_latam_identification_type_id.id or False,
            'vat': application._wk_normalize_vat(application.vat),
        }
        vals.update({
            key: value for key, value in identification_vals.items() if value
        })
        return vals

    def _ensure_related_partner(self):
        """Reimplementa wk_school_management/models/student_student.py::_ensure_related_partner
        (Webkul v5.0.4) para resolver la duplicidad de contactos (tarea 11151).

        Cambios respecto al original:

        1. Antes de buscar por correo electronico se busca el contacto por
           tipo + numero de identificacion tomados de la solicitud. El correo
           no es un criterio unico y era la causa de que se crearan contactos
           repetidos para la misma persona.
        2. Cuando el contacto se reutiliza (existia antes y no estaba ligado a
           este estudiante) solo se completan los campos que esten vacios. El
           criterio de aceptacion 19 exige no modificar automaticamente
           registros existentes.
        3. El enlace partner_id se escribe con skip_student_partner_sync para
           que _sync_to_related_partner no vuelva a volcar todos los datos del
           estudiante sobre el contacto justo despues (era lo que sobrescribia
           el correo y la direccion del contacto reutilizado). Los valores ya
           se escribieron unas lineas antes.

        El resto del comportamiento -marcar is_student, ignorar contactos que
        solo son acudientes y enlazar partner_id- se conserva sin cambios.
        """
        Partner = self.env['res.partner']
        for student in self:
            partner = student.partner_id
            reused = False
            if partner and partner.is_parent and not partner.is_student:
                partner = False
            if not partner:
                reuse_partner_id = self.env.context.get('wk_reuse_partner_id')
                if reuse_partner_id:
                    partner = self.env['res.partner'].browse(
                        reuse_partner_id).exists()
                    reused = bool(partner)
            if not partner:
                partner = student._wk_find_partner_by_identification()
                reused = bool(partner)
            if not partner:
                partner = Partner.search([
                    ('email', '=', student.email),
                    ('is_student', '=', True),
                ], limit=1)
            partner_vals = student._prepare_related_partner_vals()
            if partner:
                if reused:
                    partner_vals = {
                        key: value for key, value in partner_vals.items()
                        if not partner[key]
                    }
                if partner_vals:
                    partner.with_context(
                        skip_partner_student_sync=True).write(partner_vals)
            else:
                partner = Partner.create(partner_vals)
            if not partner.is_student:
                partner.is_student = True
            if student.partner_id != partner:
                student.with_context(
                    skip_student_partner_sync=True).partner_id = partner

    def _wk_log_academic_status_change(self, new_status, change_type, reason=None, related_class=False):
        """Registra en el histórico un cambio de Estado académico.

        Requerimiento "Estados académicos del estudiante" (2.9, 2.15): se
        llama SIEMPRE antes de escribir el nuevo valor en ``academic_status``,
        para poder capturar el estado anterior. ``related_class`` (2.14) deja
        constancia de qué Clase ofertada originó el cambio -la que se activó/
        desactivó, o a la que se (re)asignó el estudiante-; no aplica en los
        cambios manuales (Aplazado).
        """
        self.ensure_one()
        self.env['wk.school.colombo.student.status.log'].create({
            'student_id': self.id,
            'state_from': self.academic_status,
            'state_to': new_status,
            'change_type': change_type,
            'reason': reason,
            'related_class_id': related_class.id if related_class else False,
        })

    def _wk_recompute_academic_status(self, change_type='automatic', related_class=False):
        """Recalcula Activado/Liberado según si el estudiante queda
        relacionado con al menos una Clase ofertada activa (2.4, 2.5, 2.12,
        2.13). Nunca toca Aplazado -ese estado solo cambia por la acción
        manual de aplazar- ni reescribe Nuevo -el requerimiento (2.3) exige
        que un estudiante que ya tuvo una asignación no vuelva a Nuevo; por
        diseño, "new" solo pasa a "activated" (primera asignación) y nunca a
        "released" (que requiere haber estado "activated" antes).
        """
        for student in self:
            active_classes = self.env['wk.school.class'].search([
                ('student_ids.student_id', '=', student.id),
                ('is_active_class', '=', True),
            ])
            new_status = False
            log_class = related_class
            if active_classes and student.academic_status != 'activated':
                new_status = 'activated'
                if not log_class or log_class not in active_classes:
                    log_class = active_classes[:1]
            elif not active_classes and student.academic_status == 'activated':
                new_status = 'released'
            if new_status:
                student._wk_log_academic_status_change(
                    new_status, change_type=change_type, related_class=log_class)
                student.academic_status = new_status

    def _wk_schedule_accounting_activity(self, reason):
        """Crea la actividad de reclasificación contable (2.8), al confirmar
        un aplazamiento. Se asigna al responsable configurado en Ajustes
        (``company_id.accounting_reclassification_user_id``); si no se ha
        configurado ninguno, se asigna a quien confirma el aplazamiento, para
        no bloquear el flujo, dejando una nota que lo explica.
        """
        self.ensure_one()
        responsible = self.company_id.accounting_reclassification_user_id
        note = _(
            "Reclasificación contable pendiente por el aplazamiento del "
            "estudiante %(student)s.\nMotivo: %(reason)s",
            student=self.display_name, reason=reason)
        if not responsible:
            responsible = self.env.user
            note += _(
                "\n\n(No hay un responsable de reclasificación contable "
                "configurado en Ajustes; esta actividad quedó asignada a "
                "quien confirmó el aplazamiento.)")
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=responsible.id,
            summary=_("Reclasificación contable por aplazamiento"),
            note=note,
        )
