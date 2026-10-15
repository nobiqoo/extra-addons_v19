# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    resolution_text_en = fields.Html(
        string='Info de resolución (inglés)',
        help='Texto de la resolución de facturación electrónica para clientes '
             'de habla inglesa. Si está vacío se usa el texto en español.')
    note_ei_en = fields.Html(
        string='Notas en fac. electrónica (inglés)',
        help='Notas de la representación gráfica para clientes de habla '
             'inglesa. Si está vacío se usa el texto en español.')
