from odoo import api, fields, models


class EdiDocumentLog(models.Model):
    _name = 'edi.document.log'
    _description = 'Transaction log Colombian E-Invoicing'

    name = fields.Char('Name')
    move_id = fields.Many2one('account.move', 'Move')
    status_code = fields.Char('Status Code')
    reason = fields.Char('Reason')
    response = fields.Text('Response')
    exec_env = fields.Char('Environment')
    type_request = fields.Char('Type')

    edi_request_file = fields.Binary('Request',
                                     copy=False)
    edi_request_fname = fields.Char('Name Request',
                                    default='Request.xml',
                                    copy=False)
