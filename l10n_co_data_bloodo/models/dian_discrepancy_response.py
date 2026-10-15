# -*- coding: utf-8 -*-

from odoo import fields, models


class DianDiscrepancyResponse(models.Model):
    _name = 'dian.discrepancy.response'
    _inherit = ['mail.thread']
    _description = 'Conceptos de corrección DIAN para notas crédito y débito'

    name = fields.Char('Nombre',
                    tracking=True)
    dian_code = fields.Char('Código DIAN',
                    tracking=True)
    type = fields.Selection([('credit', 'Credit Note'),
                             ('debit', 'Debit Note')],
                            'Tipo',
                            tracking=True)
    is_sd = fields.Boolean('Es doc soporte?',
                    default=False,
                    tracking=True)
    is_ei = fields.Boolean('Es factura electrónica?',
                    default=False,
                    tracking=True)

