# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import ValidationError

EVENT_CODES = [
    ('02', '[02] Documento validado por la DIAN'),
    ('04', '[03] Documento rechazado por la DIAN'),
    ('030', '[030] Acuse de recibo'),
    ('031', '[031] Reclamo'),
    ('032', '[032] Recibo del bien'),
    ('033', '[033] Aceptación expresa'),
    ('034', '[034] Aceptación Tácita'),
    ('other', 'Otro')
]


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'

    fe_correction_id = fields.Many2one('dian.discrepancy.response',
                                    'Concepto de corrección',
                                    domain=[('type', '=', 'debit')])

    def create_debit(self):
        action = super(AccountDebitNote, self).create_debit()
        if action.get('res_id'):
            debit_move = self.env['account.move'].browse(action['res_id'])
            debit_move.fe_correction_id = self.fe_correction_id.id
            debit_move.type_note = 'debit'
            debit_move.fe_operation_type = '30'
            debit_move.invoice_payment_term_id = \
                debit_move.debit_origin_id.invoice_payment_term_id.id \
                    or False
            debit_move.operation_type_ei_ref = debit_move.debit_origin_id.fe_operation_type
        return action
