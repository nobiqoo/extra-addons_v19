# -*- coding: utf-8 -*-
from odoo import fields, models

from .application_form import ESTRATO_SELECTION


class ResPartner(models.Model):
    """Espejo de los campos generales del aspirante en el Contacto.

    Ronda de ajustes post-prueba: estos campos ya existían en
    wk.application.form y en student.student (requerimiento de campos
    académicos), pero nunca se habían agregado a res.partner ni a
    student.student._SYNC_FIELD_MAP/_prepare_related_partner_vals(), así que
    nunca llegaban al Contacto del estudiante. Se declaran aquí con el mismo
    tipo y las mismas opciones que en student.student
    (models/student_student.py) para que el "espejo" sea exacto.
    """

    _inherit = 'res.partner'

    program_type_id = fields.Many2one(
        'wk.school.colombo.program.type', string="Tipo de programa")
    barrio = fields.Char(string="Barrio / corregimiento")
    city_id = fields.Many2one(
        'res.city', string="Ciudad o municipio",
        domain="[('state_id', '=?', state_id)]")
    issuance_city_id = fields.Many2one(
        'res.city', string="Municipio de expedición del documento")
    origin_city_id = fields.Many2one(
        'res.city', string="Municipio / lugar de origen")
    origin_city_dian_code = fields.Char(
        related='origin_city_id.dian_code', string="Código DIAN lugar de origen")
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
    estrato = fields.Selection(ESTRATO_SELECTION, string="Estrato")
    regimen_salud = fields.Many2one(
        'wk.school.colombo.health.regime', string="Régimen de salud")
    jornada = fields.Many2one(
        'wk.school.colombo.jornada', string="Jornada")
