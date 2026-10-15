# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    invoice_label = fields.Char(
        string='Nombre en factura',
        translate=True,
        help='Nombre con el que se agrupa esta categoría en la representación '
             'gráfica de la factura (p. ej. Clavel). Si se deja vacío se usa el '
             'nombre de la categoría. Se puede traducir para los clientes de habla '
             'inglesa.')
