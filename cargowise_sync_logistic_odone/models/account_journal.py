# -*- coding: utf-8 -*-

from odoo import fields, models, _


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_default_cw = fields.Boolean(
        'Diario por defecto CW',
        default=False,
        help='Indica el diario cargado por defecto '
        'en las facturas enviadas por CargoWise. '
        '(Se debe seleccionar un diario para compras y uno para ventas).'
    )
