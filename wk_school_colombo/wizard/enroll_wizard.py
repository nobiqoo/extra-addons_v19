# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EnrollWizard(models.TransientModel):
    """Valida duplicidad por documento antes de crear contacto y estudiante.

    Tarea 11151: al abrir 'Inscribir Estudiante' se consulta si el tipo y
    numero de identificacion de la solicitud ya existen como contacto o como
    estudiante (activos y archivados) y se guia al usuario segun el caso.

    Validacion de duplicados (subtarea 2): ademas de esa validacion exacta
    -que se conserva intacta y sigue bloqueando en ``enroll_now`` cuando
    corresponde-, se agrega un paso previo de revision humana con una
    busqueda mas amplia (nombre, fecha de nacimiento, identificacion, nivel
    academico). El asistente pasa a tener dos pantallas controladas por
    ``step``: "duplicates" (solo si la busqueda amplia encuentra algo) y
    "confirm" (el contenido que el asistente ya tenia).
    """

    _inherit = 'wk.enroll.wizard'

    step = fields.Selection([
        ('duplicates', "Posibles coincidencias"),
        ('confirm', "Confirmar inscripción"),
    ], default='confirm')
    duplicate_line_ids = fields.One2many(
        'wk.enroll.wizard.duplicate.line', 'wizard_id',
        string="Posibles coincidencias")
    # Contacto que el usuario eligio reutilizar desde una fila de tipo
    # "Contacto sin estudiante" (requerimiento 2.7). Se lee en enroll_now()
    # para pasarlo como pista a student.student._ensure_related_partner()
    # cuando se crea el estudiante nuevo.
    wk_reuse_partner_id = fields.Many2one(
        'res.partner', string="Contacto a reutilizar", readonly=True)

    wk_duplicate_state = fields.Selection(
        selection=[
            ('none', "Sin coincidencias"),
            ('student', "Estudiante existente"),
            ('partner', "Contacto existente"),
            ('archived', "Registro archivado"),
        ],
        string="Resultado de la validación",
        default='none',
        readonly=True)
    wk_duplicate_message = fields.Text(
        string="Mensaje de validación", readonly=True)
    wk_matched_partner_id = fields.Many2one(
        comodel_name='res.partner', string="Contacto encontrado", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        application = self._wk_get_application()
        if not application:
            return res
        matches = application._wk_find_identification_matches()
        res.update(self._wk_prepare_duplicate_vals(matches))

        duplicates = application._wk_find_possible_duplicates()
        if duplicates:
            res['step'] = 'duplicates'
            res['duplicate_line_ids'] = [
                (0, 0, {
                    'student_id': row['student'].id if row['student'] else False,
                    'partner_id': row['partner'].id,
                    'matched_criteria': ', '.join(row['matched']),
                })
                for row in duplicates
            ]
        else:
            res['step'] = 'confirm'
        return res

    @api.model
    def _wk_get_application(self):
        application_id = self.env.context.get('active_id')
        if not application_id \
                or self.env.context.get('active_model') not in (
                    False, 'wk.application.form'):
            return self.env['wk.application.form'].browse()
        return self.env['wk.application.form'].browse(application_id).exists()

    @api.model
    def _wk_prepare_duplicate_vals(self, matches):
        """Traduce las coincidencias encontradas en valores del asistente."""
        student = matches['student'][:1]
        partner = matches['partner'][:1]
        archived_student = matches['archived_student'][:1]
        archived_partner = matches['archived_partner'][:1]

        if student:
            return {
                'wk_duplicate_state': 'student',
                'wk_matched_partner_id': student.partner_id.id,
                'student_id': student.id,
                'enroll_action': 'exist',
                'wk_duplicate_message': _(
                    "La persona ya se encuentra registrada como estudiante "
                    "(%(student)s) con el mismo tipo y número de "
                    "identificación.\nContinúe mediante la opción «Enlace a un "
                    "estudiante existente»; no se creará un contacto ni un "
                    "estudiante nuevo.",
                    student=student.display_name or student.name),
            }
        if partner:
            return {
                'wk_duplicate_state': 'partner',
                'wk_matched_partner_id': partner.id,
                'enroll_action': 'new',
                'wk_duplicate_message': _(
                    "Ya existe el contacto «%(partner)s» con la misma "
                    "identificación, pero aún no está registrado como "
                    "estudiante.\nSe reutilizará ese contacto y sólo se creará "
                    "el registro académico de estudiante.",
                    partner=partner.display_name or partner.name),
            }
        if archived_student or archived_partner:
            archived = archived_student or archived_partner
            return {
                'wk_duplicate_state': 'archived',
                'wk_matched_partner_id': archived_partner[:1].id,
                'wk_duplicate_message': _(
                    "Existe un registro archivado con la misma identificación: "
                    "%(record)s.\nNo es posible continuar hasta que dicho "
                    "registro sea revisado por un usuario responsable. El "
                    "sistema no desarchiva registros automáticamente.",
                    record=archived.display_name or archived.name),
            }
        return {'wk_duplicate_state': 'none', 'wk_duplicate_message': False}

    def enroll_now(self):
        """Bloquea la creacion de duplicados antes de ejecutar la inscripcion.

        La reutilizacion del contacto existente no se hace aqui: el estudiante
        se crea con la solicitud enlazada y student.student._ensure_related_partner
        localiza el contacto por tipo y numero de identificacion.
        """
        self.ensure_one()
        if self.enroll_action == 'new':
            application = self._wk_get_application()
            if application:
                application._wk_check_identification_data()
                matches = application._wk_find_identification_matches()
                if matches['archived_student'] or matches['archived_partner']:
                    archived = (matches['archived_student']
                                or matches['archived_partner'])[:1]
                    raise UserError(_(
                        "No se puede crear el estudiante: ya existe un "
                        "registro archivado con el mismo tipo y número de "
                        "identificación (%(record)s).\nRevise dicho registro "
                        "antes de continuar.",
                        record=archived.display_name or archived.name))
                if matches['student']:
                    student = matches['student'][:1]
                    raise UserError(_(
                        "La persona ya está registrada como estudiante "
                        "(%(student)s).\nSeleccione «Enlace a un estudiante "
                        "existente» para vincular la inscripción sin crear un "
                        "duplicado.",
                        student=student.display_name or student.name))
        elif not self.student_id:
            raise UserError(
                _("Seleccione el alumno que desea vincular a la inscripción."))
        # Si el usuario eligio reutilizar un contacto desde la pantalla de
        # posibles coincidencias (requerimiento 2.7), se pasa como pista para
        # que student.student._ensure_related_partner() lo use directamente
        # en vez de (o ademas de) su propia busqueda por identificacion.
        wizard = self
        if self.enroll_action == 'new' and self.wk_reuse_partner_id:
            wizard = self.with_context(
                wk_reuse_partner_id=self.wk_reuse_partner_id.id)
        result = super(EnrollWizard, wizard).enroll_now()
        application = self._wk_get_application()
        if self.enroll_action == 'new':
            self._wk_copy_application_fields_to_student(
                application, application.student_id, only_empty=False)
        else:
            # Estudiante ya existente ("Enlace a un estudiante existente"):
            # el criterio "se conserva al crear O VINCULAR el estudiante"
            # también aplica aquí. Se completan solo los campos que el
            # estudiante tenga vacíos -mismo criterio que la tarea 11151 usa
            # para no pisar datos ya cargados de un registro existente-.
            self._wk_copy_application_fields_to_student(
                application, self.student_id, only_empty=True)
        return result

    def _wk_copy_application_fields_to_student(self, application, student, only_empty):
        """Traslada al estudiante los campos generales de la solicitud.

        Requerimiento de campos académicos, criterio "los campos registrados
        en la aplicación deberán conservar su información cuando el proceso
        continúe hacia la creación O VINCULACIÓN del estudiante". Con
        ``only_empty=True`` (estudiante ya existente) solo se completan las
        llaves cuyo valor actual en el estudiante está vacío, para no
        sobrescribir información que el estudiante ya tenía.
        """
        if not (application and student):
            return
        vals = {
            'program_type_id': application.program_type_id.id,
            'street': application.street,
            'barrio': application.barrio,
            'city_id': application.city_id.id,
            'issuance_city_id': application.issuance_city_id.id,
            'origin_city_id': application.origin_city_id.id,
            'tipo_persona': application.tipo_persona,
            'estado_civil': application.estado_civil,
            'nivel_formacion': application.nivel_formacion,
            'idioma_nativo': application.idioma_nativo,
            'idioma_nativo_otro': application.idioma_nativo_otro,
            'ocupacion_actual': application.ocupacion_actual,
            'landline_phone': application.landline_phone,
            'additional_phone': application.additional_phone,
            'additional_mobile': application.additional_mobile,
            'email_dian': application.email_dian,
            'contact_preference': application.contact_preference,
        }
        if only_empty:
            vals = {key: value for key, value in vals.items() if not student[key]}
        if vals:
            student.write(vals)
        # Se reasignan (no se duplican) los acudientes ya cargados en la
        # solicitud: el mismo registro queda visible tanto en la solicitud
        # como en el estudiante.
        if application.guardian_ids:
            application.guardian_ids.write({'student_id': student.id})
        # El comentario libre de la solicitud se convierte en observación al
        # crear la inscripción, no aquí: en este punto todavía no existe
        # ninguna inscripción a la cual ligarla (el asistente base solo abre
        # el formulario de Inscripción, sin guardarlo). Ver
        # models/student_enrollment.py::create().

    def _wk_reopen_action(self):
        """Reabre este mismo asistente (para avanzar de "duplicates" a "confirm")."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wk.enroll.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm_new(self):
        """Botón "Ninguna coincidencia, crear nuevo" de la pantalla de coincidencias.

        Requerimiento de validación de duplicados 2.6/escenario 21: confirmar
        la creación de un nuevo registro frente a posibles coincidencias
        requiere un perfil autorizado (Officer/Admin). El botón ya está
        oculto para Staff en la vista (``groups=``); esta comprobación en
        Python cubre además llamadas por otra vía (API, automatizaciones).
        """
        self.ensure_one()
        if not self.env.user.has_group(
                'wk_school_management.wk_school_management_officer_group'):
            raise UserError(_(
                "Solo un usuario autorizado (Officer o Admin) puede "
                "confirmar la creación de un nuevo estudiante cuando existen "
                "posibles coincidencias."))
        self.write({'step': 'confirm', 'enroll_action': 'new'})
        return self._wk_reopen_action()


class EnrollWizardDuplicateLine(models.TransientModel):
    """Una fila de la pantalla de posibles coincidencias.

    Requerimiento de validación de duplicados 2.4: nombre completo, fecha de
    nacimiento, tipo/número de identificación, nivel académico, correo,
    celular y estado del estudiante, para que el usuario compare contra los
    datos de la solicitud antes de decidir.
    """

    _name = 'wk.enroll.wizard.duplicate.line'
    _description = 'Posible coincidencia de estudiante/contacto'

    wizard_id = fields.Many2one(
        'wk.enroll.wizard', required=True, ondelete='cascade')
    # Vacio cuando la fila es un Contacto sin Estudiante asociado
    # (requerimiento 2.7): en ese caso solo hay partner_id.
    student_id = fields.Many2one('student.student')
    partner_id = fields.Many2one('res.partner', required=True)
    matched_criteria = fields.Char(string="Coincide en")

    name = fields.Char(related='partner_id.name', string="Nombre completo")
    dob = fields.Date(related='student_id.dob', string="Fecha de nacimiento")
    l10n_latam_identification_type_id = fields.Many2one(
        related='partner_id.l10n_latam_identification_type_id',
        string="Tipo de identificación")
    vat = fields.Char(related='partner_id.vat', string="Número de identificación")
    grade_id = fields.Many2one(
        'wk.school.grade', string="Nivel académico", compute='_compute_grade_id')
    # Se prefiere el dato propio del Estudiante (mas probable que este
    # actualizado que el del Contacto vinculado); en una fila de tipo
    # "Contacto sin estudiante" se usa el del Contacto como respaldo. res.partner
    # no tiene campo "mobile" propio en esta version de Odoo (solo "phone").
    email = fields.Char(string="Correo electrónico", compute='_compute_email')
    mobile = fields.Char(string="Celular", compute='_compute_mobile')
    status = fields.Char(string="Estado", compute='_compute_status')

    @api.depends('student_id.current_grade_id')
    def _compute_grade_id(self):
        for line in self:
            line.grade_id = line.student_id.current_grade_id

    @api.depends('student_id.email', 'partner_id.email')
    def _compute_email(self):
        for line in self:
            line.email = line.student_id.email or line.partner_id.email

    @api.depends('student_id.mobile', 'partner_id.phone')
    def _compute_mobile(self):
        for line in self:
            line.mobile = line.student_id.mobile or line.partner_id.phone

    @api.depends('student_id.active', 'student_id.current_enrollment_id.state')
    def _compute_status(self):
        for line in self:
            if not line.student_id:
                line.status = _("Contacto sin estudiante")
            elif not line.student_id.active:
                line.status = _("Archivado")
            elif line.student_id.current_enrollment_id:
                state = line.student_id.current_enrollment_id.state
                selection = dict(
                    line.student_id.current_enrollment_id
                    ._fields['state']._description_selection(self.env))
                line.status = selection.get(state, state)
            else:
                line.status = _("Activo, sin inscripción en curso")

    def action_use_line(self):
        """Botón "Usar este registro": pasa el asistente al paso "confirm"
        con la selección ya hecha (estudiante existente, o el contacto a
        reutilizar si la fila era de tipo "Contacto sin estudiante")."""
        self.ensure_one()
        vals = {'step': 'confirm'}
        if self.student_id:
            vals['enroll_action'] = 'exist'
            vals['student_id'] = self.student_id.id
        else:
            vals['enroll_action'] = 'new'
            vals['wk_reuse_partner_id'] = self.partner_id.id
        self.wizard_id.write(vals)
        return self.wizard_id._wk_reopen_action()
