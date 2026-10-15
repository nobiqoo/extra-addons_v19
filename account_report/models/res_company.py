# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Parametrización de los valores que en la v16 de Distritodo estaban
    # quemados en el SQL del reporte (ids de BD y códigos de cuenta).
    ocr_opening_journal_id = fields.Many2one(
        'account.journal',
        string='Diario de saldos iniciales (Cartera)',
        help='Diario cuyas líneas usan la "Fecha de apertura" como fecha de '
             'factura en los informes de Cartera y DataCredito.')
    ocr_advance_account_prefix = fields.Char(
        string='Prefijos cuentas de anticipos (Cartera)',
        default='280505',
        help='Prefijos de cuenta, separados por coma, de los anticipos que '
             'se incluyen como saldo a favor en el informe de Cartera '
             '(ej: 280505,280595).')
    ocr_cartera_extra_account_ids = fields.Many2many(
        'account.account', 'ocr_cartera_extra_account_company_rel',
        'company_id', 'account_id',
        string='Cuentas adicionales (Cartera)',
        help='Cuentas que el informe de Cartera consulta siempre, además de '
             'las de tipo "Por cobrar" y los prefijos de anticipos, sin '
             'importar su tipo. El informe muestra todo el movimiento '
             'pendiente de estas cuentas.')
    ocr_collection_account_prefix = fields.Char(
        string='Prefijo cuentas de cartera (Recaudo)',
        default='1305',
        help='Prefijo de las cuentas por cobrar consideradas en el informe '
             'de Recaudo.')
    ocr_collection_excluded_accounts = fields.Char(
        string='Cuentas excluidas (Recaudo)',
        default='13050510,13050511,13050521,13050522,13050523,13050529,'
                '13050533,13050535,13050537,13050538',
        help='Códigos de cuenta, separados por coma, que se excluyen del '
             'informe de Recaudo.')
    ocr_collection_excluded_journal_codes = fields.Char(
        string='Diarios excluidos (Recaudo)',
        default='POSS%,SA,PSM',
        help='Códigos de diario, separados por coma, que se excluyen por '
             'defecto del informe de Recaudo. Admite el comodín %.')
    ocr_datacredito_excluded_accounts = fields.Char(
        string='Cuentas excluidas (DataCredito)',
        default='13050510,13050511,13050521,13050522,13050523,13050529,'
                '13050532,13050533,13050535,13050536,13050537,13050538,'
                '13050539,13990101',
        help='Códigos de cuenta, separados por coma, que se excluyen del '
             'informe DataCredito.')
    ocr_datacredito_excluded_prefixes = fields.Char(
        string='Prefijos excluidos (DataCredito)',
        default='1330,1310,1365,1399,1390',
        help='Prefijos de cuenta, separados por coma, que se excluyen del '
             'informe DataCredito.')
    ocr_excluded_partner_vats = fields.Char(
        string='Identificaciones excluidas (Recaudo)',
        default='222222222222,999999999',
        help='Números de identificación de contactos genéricos, separados '
             'por coma, que se excluyen del informe de Recaudo.')

    def _ocr_split_param(self, value):
        """Convierte un parámetro separado por comas en lista limpia."""
        return [v.strip() for v in (value or '').split(',') if v.strip()]
