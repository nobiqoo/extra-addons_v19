# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EdiHrLog(models.Model):
    _name = 'edi.hr.log'
    _description = 'Log de transacción Nómina Electrónica Colombiana'

    name = fields.Char('Name')
    hr_id = fields.Many2one('hr.payslip',
                            'Payslip')
    edi_hr_id = fields.Many2one('edi.hr.document',
                                'Documento electrónico')
    status_code = fields.Char('Status Code')
    reason = fields.Char('Reason')
    response = fields.Text('Response')
    exec_env = fields.Char('Environment')
    type_request = fields.Char('Type')

    edi_request_file = fields.Binary('Request', copy=False)
    edi_request_fname = fields.Char('Name Request',
                                    default='Request.xml',
                                    copy=False)
