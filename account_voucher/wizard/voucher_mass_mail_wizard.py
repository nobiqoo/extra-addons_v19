# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class VoucherMassMailWizard(models.AbstractModel):
    _name = 'voucher.mass.mail.wizard'

    date_from = fields.Date('Fecha inicio')
    date_to = fields.Date('Fecha fin')
    partner_ids = fields.Many2many('res.partner',
                                   'Terceros')
    voucher_ids = fields.Many2many('account.voucher',
                                   'Documentos de pago')
