# -*- coding: utf-8 -*-

from odoo import fields, models, _


class VoucherMailError(models.Model):
    _name = 'voucher.mail.error'
    _description = 'Log de errores en correos de pagos'

    name = fields.Char('Nombre')
    voucher_id = fields.Many2one('account.voucher',
                                 'Doc. pago')
    error_txt = fields.Text('Detalle')
