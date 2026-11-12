# -*- coding: utf-8 -*-
from odoo import fields, models


class WkSchoolColomboJornada(models.Model):
    """Catálogo configurable de Jornada.

    Requerimiento (punto 10): Diurna/Nocturna/Fin de semana ya no es un
    Selection fijo -se necesita poder agregar más sin tocar código-. Mismo
    patrón mínimo que wk.school.colombo.sede.
    """

    _name = 'wk.school.colombo.jornada'
    _description = 'Jornada'
    _order = 'sequence, name'

    name = fields.Char(string="Nombre", required=True)
    sequence = fields.Integer(default=1)
    active = fields.Boolean(
        'Activo', default=True,
        help="Al desmarcarla, la jornada deja de estar disponible para "
             "nuevas selecciones, pero las que ya la usan conservan la "
             "información sin cambios.")
