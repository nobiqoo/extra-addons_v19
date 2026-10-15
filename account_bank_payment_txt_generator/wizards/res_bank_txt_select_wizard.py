# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResBankTxtSelectWizard(models.TransientModel):
    _name = 'res.bank.txt.select.wizard'
    _description = 'Wizard to select bank txt config'

    txt_doc_id = fields.Many2one('res.bank.txt_config', 'Txt format')
    order_id = fields.Many2one('account.payment.order', 'Payment order')
    bank_id = fields.Many2one('res.bank', 'Bank')
    msg = fields.Text('Message')

    def generate_txt(self):
        self.order_id._generate_txt(self.txt_doc_id)
