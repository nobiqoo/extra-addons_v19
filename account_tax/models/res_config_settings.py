# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    calculate_ica_by_line = fields.Boolean(
        string="Calcular ICA por Línea",
        related='company_id.calculate_ica_by_line',
        readonly=False,
        help="Si está activado, los impuestos de ICA se calcularán individualmente para cada línea de factura. "
             "Si está desactivado, se calcularán globalmente en la factura."
    )