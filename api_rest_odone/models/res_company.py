# -*- coding: utf-8 -*-

import secrets

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    api_integration_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario para Integración API',
        domain="[('type', 'in', ['general', 'sale', 'purchase']), ('company_id', '=', id)]",
        help=(
            'Diario contable que se utilizará para registrar los asientos '
            'creados mediante el endpoint REST de integración.'
        ),
    )

    api_rest_api_key = fields.Char(
        string='API Key de Integración',
        copy=False,
        groups='base.group_system',
        help=(
            'Clave secreta de autenticación para el endpoint REST de asientos contables. '
            'El sistema externo debe enviarla en el header HTTP: X-API-Key: <clave>. '
            'Use el botón "Generar" para crear una clave segura automáticamente.'
        ),
    )

    def action_generate_api_rest_key(self):
        """Genera una API Key segura aleatoria de 256 bits de entropía."""
        self.ensure_one()
        self.api_rest_api_key = secrets.token_urlsafe(32)
