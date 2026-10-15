# -*- coding: utf-8 -*-
from odoo import fields, models


class WkSchoolColomboProgramType(models.Model):
    """Catálogo configurable de Tipo de programa.

    Requerimiento de campos académicos: el Tipo de programa no debe depender
    de valores fijos en código. Se modela como catálogo independiente (mismo
    patrón mínimo que wk.class.location) para que un usuario autorizado pueda
    crear, modificar y activar/desactivar tipos sin necesitar un desarrollo
    nuevo. La selección de un tipo no dispara ningún comportamiento
    académico: es puramente descriptivo.
    """

    _name = 'wk.school.colombo.program.type'
    _inherit = 'wk.company.visibility.mixin'
    _description = 'Tipo de programa'
    _order = 'sequence, name'

    name = fields.Char(string="Nombre", required=True)
    sequence = fields.Integer(default=1)
    company_id = fields.Many2one(
        'res.company', string="Sede", default=lambda self: self.env.company,
        required=True)
    active = fields.Boolean(
        'Activo', default=True,
        help="Al desmarcarlo, el tipo de programa deja de estar disponible "
             "para nuevas solicitudes, pero las que ya lo usan conservan la "
             "información sin cambios.")
