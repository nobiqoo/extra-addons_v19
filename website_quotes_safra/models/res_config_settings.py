# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Parámetros de la fórmula Best Fit de Panel Track (P19), editables
    por el cliente sin modo desarrollador. Se guardan como parámetros del
    sistema; si están vacíos rigen los valores del documento «Formula
    Final» (telo 0.35–0.95 m, persiana 8 m, rieles 4/5/6)."""
    _inherit = 'res.config.settings'

    safra_panel_telo_min = fields.Float(
        string='Ancho mínimo del telo (m)', default=0.35,
        config_parameter='safra.panel.ancho_telo_min')
    safra_panel_telo_max = fields.Float(
        string='Ancho máximo del telo (m)', default=0.95,
        config_parameter='safra.panel.ancho_telo_max')
    safra_panel_ancho_max = fields.Float(
        string='Ancho máximo de la persiana (m)', default=8.0,
        config_parameter='safra.panel.ancho_max')
    safra_panel_rieles = fields.Char(
        string='Rieles disponibles (canales)', default='4,5,6',
        config_parameter='safra.panel.rieles',
        help='Cantidades de canales separadas por coma, ej: 4,5,6')
