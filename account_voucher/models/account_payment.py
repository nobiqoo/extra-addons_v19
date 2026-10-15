# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    immediate_payment = fields.Boolean('Immediate Payment ?')
