# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import ValidationError

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF'
}


class PortfolioDetailWizard(models.TransientModel):
    _name = "portfolio.detail.wizard"
    _description = "Portfolio Detail Wizard"

    partner_ids = fields.Many2many('res.partner', string="Partners")
    find_by = fields.Selection(
        [
            ('date', 'Date'),
            ('invoice', 'Invoice')
        ], string="Find By", default='date'
    )
    date_from = fields.Date(string="Date from")
    date_to = fields.Date(string="Date to")
    move_ids = fields.Many2many(
        'account.move', 'portfolio_detail_move_ids', 'portfolio_id', 'move_id', string="Moves")
    report_type = fields.Selection(
        [
            ('pdf', 'PDF'),
            ('excel', 'EXCEL')
        ], string="Report type", default='pdf'
    )
    line_ids = fields.One2many(
        'portfolio.detail.wizard.line', 'wizard_id', string="Lines")
    partners_involved = fields.Char(string="Partners involved")

    def create_report(self):
        for line in self.line_ids:
            line.unlink()
        if self.find_by == 'date':
            domain = [
                ('invoice_date', '>=', self.date_from),
                ('invoice_date', '<=', self.date_to),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('paid', 'partial')),
                ('partner_id', 'in', self.partner_ids.ids)
            ]
            invoices = self.env['account.move'].search(domain)
        else:
            invoices = self.move_ids
        if len(invoices) == 0:
            raise ValidationError(_('No results found for this search.'))
        invoice_lines = self.find_payment_methods(invoices)
        self.create_payment_methods(invoice_lines)
        self.get_partners_involved_names(invoice_lines)
        return self.generate_file()

    def get_partners_involved_names(self, invoice_lines):
        names = []
        for invoice_line in invoice_lines:
            if invoice_line[1] not in names:
                names.append(invoice_line[1])
        self.partners_involved = ";".join(names)

    def format_currency(self, number_format):
        return '$' + "{:,}".format(round(float(number_format), 2))

    def generate_file(self):
        if self.report_type == 'pdf':
            return self.env.ref('portfolio_detail.portfolio_detail_template_action').report_action(self)
        else:
            return self.download_report_excel()

    def download_report_pdf(self):
        return self.env.ref('sale_commissions.sale_commission_report_template_action').report_action(self)

    def download_report_excel(self):
        portfolio_print = self.env['portfolio.detail.print.xlsx'].create({
            'report_id': self.id
        })
        return portfolio_print.create_xlsx_file()

    def find_payment_methods(self, invoices):
        payment_method_lines = []
        for inv in invoices:
            pending_amount = inv.amount_total
            payments = inv._get_all_reconciled_invoice_partials()
            invoice_payments = []
            for payment in payments:
                counterpart_line = payment['aml']
                if counterpart_line.move_id.ref:
                    reconciliation_ref = '%s (%s)' % (
                        counterpart_line.move_id.name, counterpart_line.move_id.ref)
                else:
                    reconciliation_ref = counterpart_line.move_id.name
                if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                    foreign_currency = counterpart_line.currency_id
                else:
                    foreign_currency = False

                payment_data = {
                    'journal_name': counterpart_line.journal_id.name,
                    'amount': payment['amount'],
                    'name': counterpart_line.name,
                    'ref': reconciliation_ref,
                    'date': counterpart_line.date,
                    'amount_company_currency': counterpart_line.balance,
                    'amount_foreign_currency': counterpart_line.amount_currency if foreign_currency else None,
                }

                pending_amount -= payment['amount']
                invoice_payments.append([
                    payment_data['journal_name'],
                    payment_data['amount'],
                    payment_data['name'],
                    payment_data['ref'],
                    str(payment_data['date']),
                    pending_amount
                ])

            payment_method_lines.append([
                inv.name,
                inv.partner_id.name,
                inv.partner_id.vat,
                inv.invoice_date,
                inv.invoice_date_due,
                inv.amount_untaxed,
                inv.amount_total,
                invoice_payments
            ])

        return payment_method_lines

    def create_payment_methods(self, invoice_lines):
        for invoice_line in invoice_lines:
            report_line = self.env['portfolio.detail.wizard.line'].create(
                {
                    'invoice': invoice_line[0],
                    'partner': invoice_line[1],
                    'nit': invoice_line[2],
                    'invoice_date': invoice_line[3],
                    'due_date': invoice_line[4],
                    'amount_untaxed': invoice_line[5],
                    'amount_total': invoice_line[6],
                    'wizard_id': self.id
                }
            )
            for line in invoice_line[7]:
                self.env['detail.wizard.line.line'].create(
                    {
                        'payment_method': line[0],
                        'amount_paid': line[1],
                        'name': line[2],
                        'ref': line[3],
                        'date': line[4],
                        'pending_amount': line[5],
                        'line_id': report_line.id
                    }
                )


class PortfolioDetailWizard(models.TransientModel):
    _name = "portfolio.detail.wizard.line"
    _description = "Portfolio Detail Wizard line"

    invoice = fields.Char(string="Invoice")
    partner = fields.Char(string="Partner")
    nit = fields.Char(string="NIT")
    invoice_date = fields.Date(string="Invoice date")
    due_date = fields.Date(string="Due date")
    amount_untaxed = fields.Char(string="Amount untaxed")
    amount_total = fields.Char(string="Amount total")
    line_ids = fields.One2many(
        'detail.wizard.line.line', 'line_id', string="Lines")
    wizard_id = fields.Many2one('portfolio.detail.wizard', string="Wizard")


class DetailWizardLineLine(models.TransientModel):
    _name = "detail.wizard.line.line"
    _description = "Detail wizard line line"

    payment_method = fields.Char(string="Payment method")
    amount_paid = fields.Float(string="Amount paid")
    line_id = fields.Many2one('portfolio.detail.wizard.line', string="Line")
    name = fields.Char(string="Name")
    ref = fields.Char(string="Ref")
    date = fields.Date(string="Payment date")
    pending_amount = fields.Float(string="Pending amount")
