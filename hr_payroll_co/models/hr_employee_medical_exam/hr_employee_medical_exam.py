from odoo import models, fields, api
from odoo.tools import html_escape
from datetime import date, timedelta


class HrEmployeeMedicalExam(models.Model):
    _name = 'medical.exam'
    _description = 'Medical Exam'
    _order = 'expiration_days'

    name = fields.Many2one('medical.exam.type', string="Type of Examination", required=True)
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    document = fields.Binary(string="Attached Document", required=True)
    document_name = fields.Char(string="Name of Document", required=True)
    document_url = fields.Html(string="Document Link", compute="_compute_document_url", store=True)
    expiration_days = fields.Integer(string="Days to Maturity", compute="_compute_expiration_days", store=True)
    insurance_type = fields.Selection(
        [('ips', 'IPS'), ('eps', 'EPS')], 
        string="IPS/EPS", 
        required=True
    )
    insurance_name = fields.Char(string="Name of Insurer", required=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, ondelete="cascade")

    @api.depends('start_date', 'end_date')
    def _compute_expiration_days(self):
        today = date.today()
        for record in self:
            if record.end_date:
                record.expiration_days = (record.end_date - today).days
            else:
                record.expiration_days = 0

    @api.depends('document', 'document_name')
    def _compute_document_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.document and record.document_name:
                record.document_url = (
                    f'<a href="{base_url}/web/content/{record._name}/{record.id}/document/{html_escape(record.document_name)}" '
                    f'download="{html_escape(record.document_name)}">{html_escape(record.document_name)}</a>'
                )
            else:
                record.document_url = ''

    @api.onchange('document')
    def _onchange_document(self):
        if self.document and not self.document_name:
            self.document_name = 'Documento.pdf'