# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    calculate_ica_by_line = fields.Boolean(
        string="Calcular ICA por Línea",
        default=False,
        help="Si está activado, los impuestos de ICA se calcularán individualmente para cada línea de factura. "
             "Si está desactivado, se calcularán globalmente en la factura."
    )