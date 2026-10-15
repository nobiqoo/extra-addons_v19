# -*- coding: utf-8 -*-
import unicodedata

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression

# Caracteres que se descartan al normalizar un numero de identificacion antes
# de compararlo o guardarlo (puntos, guiones, espacios y comas de miles).
VAT_SEPARATORS = ' .,-'

NAME_STOPWORDS = {'de', 'del', 'la', 'las', 'los', 'y'}

DUPLICATE_MATCH_THRESHOLD = 2


class WkApplicationForm(models.Model):
    """Solicitud de inscripcion con los datos de identificacion del solicitante.

    Tarea 11151: la solicitud pasa a ser la fuente de informacion del contacto
    y del estudiante. Se agregan los mismos campos que maneja Contactos en la
    localizacion colombiana (name1/name2/lastname1/lastname2 de
    l10n_co_data_bloodo y l10n_latam_identification_type_id/vat de
    l10n_latam_base) para poder validar duplicidad por documento antes de crear
    registros nuevos.
    """

    _inherit = 'wk.application.form'

    # Tarea 11152: la fotografia deja de ser obligatoria. Durante la etapa
    # inicial de solicitud la institucion todavia esta recopilando la
    # informacion basica del aspirante y la foto no es el criterio de
    # identificacion (eso lo resuelven los nombres y el documento de la tarea
    # 11151). El campo sigue disponible y se puede diligenciar despues en la
    # solicitud, en el contacto o en el registro del estudiante.
    student_image = fields.Image(required=False)

    name1 = fields.Char(string="Primer nombre", tracking=True)
    name2 = fields.Char(string="Segundo nombre", tracking=True)
    lastname1 = fields.Char(string="Primer apellido", tracking=True)
    lastname2 = fields.Char(string="Segundo apellido", tracking=True)
    l10n_latam_identification_type_id = fields.Many2one(
        comodel_name='l10n_latam.identification.type',
        string="Tipo de identificación",
        tracking=True,
        default=lambda self: self.env.ref(
            'l10n_co.national_citizen_id', raise_if_not_found=False),
        help="Tipo de documento del solicitante. Se reutilizan los mismos "
             "tipos disponibles en Contactos.")
    vat = fields.Char(
        string="Número de identificación",
        tracking=True,
        help="Numero de documento del solicitante. Junto con el tipo de "
             "identificacion es el criterio usado para validar si la persona "
             "ya existe como contacto o como estudiante.")

    # Campos generales del estudiante/aplicación (requerimiento de campos
    # académicos). Se conservan aquí y se copian al estudiante al inscribir
    # (wizard/enroll_wizard.py) para que la información no se vuelva a
    # diligenciar.
    program_type_id = fields.Many2one(
        'wk.school.colombo.program.type', string="Tipo de programa",
        required=True, tracking=True,
        help="Catálogo configurable en Configuración. No genera por sí solo "
             "ningún comportamiento académico diferenciado.")
    street = fields.Char(required=True)
    barrio = fields.Char(string="Barrio / corregimiento", required=True)
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
    ], string="Tipo de persona", default='natural', tracking=True)
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
    age = fields.Integer(
        string="Edad", compute='_compute_age',
        help="Calculada a partir de la fecha de nacimiento.")
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
    application_comment = fields.Text(string="Comentarios")
    # El comentario se traslada como observación a la PRIMERA inscripción que
    # se cree a partir de esta solicitud (student.enrollment.create(), en
    # models/student_enrollment.py) -no al inscribir, momento en el que la
    # inscripción todavía no existe-. Este flag evita convertirlo dos veces
    # si el estudiante llega a tener varias inscripciones despues.
    application_comment_converted = fields.Boolean(default=False)
    guardian_ids = fields.One2many(
        'wk.school.colombo.guardian', 'application_id', string="Acudientes")

    NAME_PARTS = ('name1', 'name2', 'lastname1', 'lastname2')

    @api.depends('dob')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for application in self:
            if not application.dob:
                application.age = 0
                continue
            dob = application.dob
            application.age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day))

    @api.model
    def _wk_build_student_name(self, values):
        """Nombre completo a partir de los nombres y apellidos separados.

        student_name se conserva porque el modulo base y el formulario del
        sitio web lo usan y es obligatorio; aqui solo se alimenta a partir de
        los campos separados. Si la solicitud no los trae (portal web,
        registros historicos) se devuelve False y el valor actual no se toca.
        """
        parts = [values.get(part) for part in self.NAME_PARTS]
        return ' '.join(part.strip() for part in parts if part) or False

    @api.onchange(*NAME_PARTS)
    def _onchange_name_parts(self):
        full_name = self._wk_build_student_name({
            part: self[part] for part in self.NAME_PARTS})
        if full_name:
            self.student_name = full_name

    @api.model
    def _wk_normalize_vat(self, vat):
        """Devuelve el numero de documento sin separadores ni espacios."""
        if not vat:
            return False
        for separator in VAT_SEPARATORS:
            vat = vat.replace(separator, '')
        return vat.strip() or False

    @api.onchange('vat', 'l10n_latam_identification_type_id')
    def _onchange_identification(self):
        """Normaliza el documento y avisa -sin bloquear- si ya esta en uso.

        No se bloquea porque depurar las solicitudes historicas esta fuera del
        alcance de la tarea 11151; la validacion que si impide duplicados se
        ejecuta al inscribir.
        """
        self.ensure_one()
        if self.vat:
            self.vat = self._wk_normalize_vat(self.vat)
        if not (self.vat and self.l10n_latam_identification_type_id):
            return
        domain = [
            ('l10n_latam_identification_type_id', '=',
             self.l10n_latam_identification_type_id.id),
            ('vat', '=', self.vat),
        ]
        if self._origin.id:
            domain.append(('id', '!=', self._origin.id))
        others = self.search(domain, limit=3)
        if others:
            return {
                'warning': {
                    'title': _("Identificación ya registrada"),
                    'message': _(
                        "Ya existen solicitudes con este tipo y número de "
                        "identificación: %s.\nVerifique que no se trate de un "
                        "registro duplicado.",
                        ', '.join(others.mapped('name'))),
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('vat'):
                vals['vat'] = self._wk_normalize_vat(vals['vat'])
            full_name = self._wk_build_student_name(vals)
            if full_name:
                vals['student_name'] = full_name
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('vat'):
            vals = dict(vals, vat=self._wk_normalize_vat(vals['vat']))
        if any(part in vals for part in self.NAME_PARTS):
            # El nombre completo se recalcula por registro, combinando los
            # valores enviados con los que ya tiene la solicitud.
            for application in self:
                values = {
                    part: vals.get(part, application[part])
                    for part in self.NAME_PARTS
                }
                full_name = self._wk_build_student_name(values)
                super(WkApplicationForm, application).write(
                    dict(vals, student_name=full_name) if full_name else vals)
            return True
        return super().write(vals)

    def _wk_check_identification_data(self):
        """Valida que la solicitud tenga los datos minimos del solicitante.

        Los campos se marcan como obligatorios en la vista de backend; esta
        validacion cubre los registros creados por otras vias (portal web,
        importaciones, solicitudes historicas) y se ejecuta antes de confirmar
        o de inscribir, que es cuando la informacion se vuelve indispensable.
        """
        required_fields = {
            'name1': _("Primer nombre"),
            'lastname1': _("Primer apellido"),
            'l10n_latam_identification_type_id': _("Tipo de identificación"),
            'vat': _("Número de identificación"),
            'dob': _("Fecha de nacimiento"),
        }
        for application in self:
            missing = [
                label for field, label in required_fields.items()
                if not application[field]
            ]
            if missing:
                raise UserError(_(
                    "Complete los siguientes campos de la solicitud %(name)s "
                    "antes de continuar:\n- %(fields)s",
                    name=application.name,
                    fields='\n- '.join(missing)))

    def _wk_find_identification_matches(self):
        """Busca contactos y estudiantes con el mismo tipo y numero de documento.

        Incluye registros archivados (active_test=False) y devuelve un dict con
        las coincidencias clasificadas. El estudiante no almacena la
        identificacion: se localiza a traves del contacto relacionado.
        """
        self.ensure_one()
        empty_partner = self.env['res.partner'].browse()
        empty_student = self.env['student.student'].browse()
        result = {
            'partner': empty_partner,
            'student': empty_student,
            'archived_partner': empty_partner,
            'archived_student': empty_student,
        }
        vat = self._wk_normalize_vat(self.vat)
        if not (vat and self.l10n_latam_identification_type_id):
            return result

        partners = self.env['res.partner'].sudo().with_context(
            active_test=False).search([
                ('l10n_latam_identification_type_id', '=',
                 self.l10n_latam_identification_type_id.id),
                ('vat', '=', vat),
            ])
        students = empty_student
        if partners:
            students = self.env['student.student'].sudo().with_context(
                active_test=False).search([('partner_id', 'in', partners.ids)])

        result['partner'] = partners.filtered('active')
        result['student'] = students.filtered('active')
        result['archived_partner'] = partners - result['partner']
        result['archived_student'] = students - result['student']
        return result

    @api.model
    def _wk_normalize_name_words(self, name):
        """Palabras significativas de un nombre, sin tildes/mayusculas/conectores.
        """
        if not name:
            return set()
        stripped = ''.join(
            char for char in unicodedata.normalize('NFKD', name)
            if not unicodedata.combining(char))
        return {
            word for word in stripped.lower().split()
            if word and word not in NAME_STOPWORDS
        }

    def _wk_score_student_match(self, student, name_words, vat):
        """Cuenta en cuantos de los 4 criterios coincide un estudiante candidato.
        """
        self.ensure_one()
        matched = []

        if name_words:
            candidate_words = self._wk_normalize_name_words(student.name)
            common = name_words & candidate_words
            if candidate_words and (
                    len(common) >= 2
                    or name_words <= candidate_words
                    or candidate_words <= name_words):
                matched.append(_("Nombre"))

        if self.dob and student.dob and student.dob == self.dob:
            matched.append(_("Fecha de nacimiento"))

        partner = student.partner_id
        if (vat and self.l10n_latam_identification_type_id
                and partner.l10n_latam_identification_type_id == self.l10n_latam_identification_type_id
                and partner.vat and self._wk_normalize_vat(partner.vat) == vat):
            matched.append(_("Identificación"))

        if self.grade_id:
            student_grades = student.enrollment_ids.grade_id | student.current_grade_id
            if self.grade_id in student_grades:
                matched.append(_("Nivel académico"))

        return len(matched), matched

    def _wk_find_fuzzy_student_matches(self):
        """Estudiantes que coinciden en 2 o mas de los 4 criterios definidos.

        Devuelve una lista de dicts (student, partner, score, matched),
        ordenada de mayor a menor coincidencia.
        """
        self.ensure_one()
        name_words = self._wk_normalize_name_words(self.student_name)
        vat = self._wk_normalize_vat(self.vat)

        sub_domains = []
        if vat and self.l10n_latam_identification_type_id:
            sub_domains.append([
                ('partner_id.l10n_latam_identification_type_id', '=',
                 self.l10n_latam_identification_type_id.id),
                ('partner_id.vat', '=', vat),
            ])
        if self.dob:
            sub_domains.append([('dob', '=', self.dob)])
        for word in name_words:
            if len(word) >= 3:
                sub_domains.append([('name', 'ilike', word)])
        if not sub_domains:
            return []

        domain = expression.OR(sub_domains)
        if self.student_id:
            domain = expression.AND([[('id', '!=', self.student_id.id)], domain])

        Student = self.env['student.student'].sudo().with_context(active_test=False)
        results = []
        for student in Student.search(domain):
            score, matched = self._wk_score_student_match(student, name_words, vat)
            if score >= DUPLICATE_MATCH_THRESHOLD:
                results.append({
                    'student': student,
                    'partner': student.partner_id,
                    'score': score,
                    'matched': matched,
                })
        results.sort(key=lambda row: row['score'], reverse=True)
        return results

    def _wk_find_possible_duplicates(self):
        """Candidatos a mostrar en la pantalla de posibles coincidencias.
        """
        self.ensure_one()
        results = self._wk_find_fuzzy_student_matches()
        matches = self._wk_find_identification_matches()
        for partner in matches['partner']:
            results.append({
                'student': self.env['student.student'].browse(),
                'partner': partner,
                'score': DUPLICATE_MATCH_THRESHOLD,
                'matched': [_("Identificación")],
            })
        return results

    def confirm_application(self):
        self._wk_check_identification_data()
        return super().confirm_application()

    def enroll_application(self):
        self._wk_check_identification_data()
        action = super().enroll_application()
        if isinstance(action, dict) and action.get('res_model') == 'wk.enroll.wizard' \
                and not action.get('res_id'):
            context = dict(self.env.context)
            action_context = action.get('context')
            if isinstance(action_context, dict):
                context.update(action_context)
            context.update({
                'active_id': self.id,
                'active_model': 'wk.application.form',
            })
            wizard = self.env['wk.enroll.wizard'].with_context(**context).create({})
            action['res_id'] = wizard.id
        return action
