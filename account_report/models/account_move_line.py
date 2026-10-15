# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Campos que existían en custom_report_account_receivable (v16). Se
    # conservan con el mismo nombre de columna para que los datos sobrevivan
    # la migración de la base.
    opening_date_due = fields.Date(
        string='Fecha de apertura',
        help='Fecha de vencimiento original de los saldos iniciales. En los '
             'informes de Cartera y DataCredito reemplaza a la fecha de '
             'factura para el diario de saldos iniciales.')
    obligation_relation = fields.Many2one(
        'account.move', string='Obligación', index='btree_not_null')
