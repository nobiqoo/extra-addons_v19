# -*- coding: utf-8 -*-
from odoo import fields, models


class WkSchoolColomboClassModality(models.Model):
    """Catálogo configurable de Modalidad.

    Requerimiento de campos académicos (ronda de ajustes post-prueba): la
    Modalidad no debe depender de valores fijos en código (sabatino, diario,
    vacacional), porque varía según la institución. Se modela como catálogo
    independiente (mismo patrón mínimo que wk.school.colombo.program.type)
    para que un usuario autorizado pueda crear, modificar y
    activar/desactivar modalidades sin necesitar un desarrollo nuevo. La
    selección de una modalidad no dispara ningún comportamiento académico: es
    puramente descriptiva.
    """

    _name = 'wk.school.colombo.class.modality'
    _inherit = 'wk.company.visibility.mixin'
    _description = 'Modalidad'
    _order = 'sequence, name'

    name = fields.Char(string="Nombre", required=True)
    sequence = fields.Integer(default=1)
    company_id = fields.Many2one(
        'res.company', string="Sede", default=lambda self: self.env.company,
        required=True)
    active = fields.Boolean(
        'Activo', default=True,
        help="Al desmarcarla, la modalidad deja de estar disponible para "
             "nuevas Clases ofertadas, pero las que ya la usan conservan la "
             "información sin cambios.")
