# -*- coding: utf-8 -*-
from odoo import fields, models


class SafraColor(models.Model):
    """Catálogo de colores (U_color).

    Lista de colores genéricos, independiente de referencias y productos
    (feedback funcional: «un listadito de colores»). Los artículos del
    maestro apuntan aquí con su campo U_color; el portal agrupa por este
    catálogo y la formulación resuelve el artículo concreto por ancho.
    """
    _name = 'safra.color'
    _description = 'Color (U_color)'
    _order = 'name'

    _name_uniq = models.Constraint('UNIQUE(name)', 'El color ya existe en el catálogo.')

    name = fields.Char(string='Color', required=True)
    active = fields.Boolean(default=True)
