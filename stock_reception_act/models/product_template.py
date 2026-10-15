# -*- coding: utf-8 -*-

from odoo import fields, models

# Clasificación de riesgo de dispositivos médicos (Decreto 4725 de 2005 - INVIMA)
RISK_CLASS_SELECTION = [
    ('i', 'Class I'),
    ('iia', 'Class IIa'),
    ('iib', 'Class IIb'),
    ('iii', 'Class III'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    commercial_presentation = fields.Char(
        string='Commercial Presentation',
    )
    sanitary_registration = fields.Char(
        string='Sanitary Registration',
        help='Sanitary registration or marketing authorization number issued by INVIMA.',
    )
    shelf_life = fields.Char(
        string='Shelf Life',
    )
    risk_class = fields.Selection(
        selection=RISK_CLASS_SELECTION,
        string='Risk Class',
    )
