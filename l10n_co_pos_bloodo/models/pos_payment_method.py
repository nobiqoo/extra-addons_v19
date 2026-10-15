# -*- coding: utf-8 -*-

from odoo import fields, models, _


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    fe_payment_option_id = fields.Many2one('dian.payment.option',
                                           'DIAN payment option')
