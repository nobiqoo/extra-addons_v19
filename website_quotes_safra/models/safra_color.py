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

    def _seed_from_portal(self):
        """Siembra el catálogo con los colores del portal y asigna U_color a
        los artículos vinculados (por nombre). Idempotente."""
        Color = self.env['safra.color'].sudo()
        existing = {c.name.strip().lower(): c for c in Color.with_context(active_test=False).search([])}
        for pcolor in self.env['safra.fabric.color'].with_context(active_test=False).sudo().search([]):
            name = (pcolor.name or '').strip()
            if not name:
                continue
            color = existing.get(name.lower())
            if not color:
                color = Color.create({'name': name})
                existing[name.lower()] = color
            elif color.name.isupper() and not name.isupper():
                # Prefiere la variante con mayúsculas/minúsculas mixtas.
                color.name = name
            product = pcolor.product_tmpl_id
            if product and not product.safra_u_color:
                product.safra_u_color = color.id
