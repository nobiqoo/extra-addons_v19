# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductUom(models.Model):
    _inherit = 'uom.uom'

    dian_country_code = fields.Char('Código país',
                                    default=lambda self: self.env.company.country_id.code)
    dian_uom_id = fields.Many2one('dian.uom.code',
                                  'UdM DIAN')
    dian_unspsc_id = fields.Many2one('product.unspsc.dian_code',
                                     'Categoría de producto UNSPSC',
                                     domain=[('applies_to', '=', 'uom')],
                                     help='Código UNSPSC relacionado a esta UdM.')

