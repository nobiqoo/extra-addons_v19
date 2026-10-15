# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

MAIL_TEMPLATE = "tax_certificate_management.withholding_certificate_report_email_template"


class WithholdingCertificateType(models.Model):
    _name = "withholding.certificate.report"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Withholding certificate report"
    _order = 'create_date desc'

    name = fields.Char(string="Name", required=True)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, default=lambda self: self.env.company)
    certificate_id = fields.Many2one(
        comodel_name='withholding.certificate.type', string="Withholding certificate type", required=True)
    certificate_period_id = fields.Many2one(
        comodel_name='certificate.period', string="Certificate period", required=True)
    periodicity = fields.Selection(
        string="Periodicity", required=True, related='certificate_period_id.periodicity')
    partner_id = fields.Many2one(
        'res.partner', string="Partner", required=True)
    line_ids = fields.One2many(
        'withholding.certificate.report.line', 'report_id', string="Tax lines")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prefix = self.env['ir.sequence'].next_by_code(
                'withholding.certificate.report')
            vals['name'] = prefix
        scr = super(WithholdingCertificateType, self).create(vals_list)
        return scr

    def send_email(self):
        self.ensure_one()
        mail_template = self.env.ref(MAIL_TEMPLATE)
        mail_template.send_mail(self.id, force_send=True)

    def print_pdf_report(self):
        return self.env.ref('tax_certificate_management.tax_certificate_management_tmpl_action').report_action(self)


class WithholdingCertificateReportLine(models.Model):
    _name = "withholding.certificate.report.line"
    _description = "Withholding certificate report line"

    tax_account = fields.Many2one(
        'account.account', string='Tax account', required=True)
    base_amount = fields.Float(string="Base amount", default=0)
    amount_withheld = fields.Float(string="Amount withheld", default=0)
    percentage = fields.Float(string="Percentage", default=0)
    movements_qty = fields.Float(string="Movements qty", default=0)
    report_id = fields.Many2one(
        'withholding.certificate.report', string="Withholding report")
    company_id = fields.Many2one('res.company', string="Company")
    tax_id = fields.Many2one('account.tax', string="Tax", required=True)
    period = fields.Char(string="Period")
    city_id = fields.Many2one('res.city', string="City")
