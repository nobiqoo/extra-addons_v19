# -*- coding: utf-8 -*-
"""Tirilla de pago (tarea 12458).

El campo "Observaciones" se captura desde el wizard estandar "Registrar
Pago" (ver models/account_payment_register.py) y queda guardado en el propio
account.payment para que la tirilla lo muestre tanto al imprimir como al
reimprimir.
"""
from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    observaciones = fields.Text(string='Observaciones')
