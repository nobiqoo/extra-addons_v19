# -*- coding: utf-8 -*-

from odoo import _, fields, models
from datetime import date
import calendar

MONTHLY_RANGE = [[1], [2], [3], [4], [5], [6], [7], [8], [9], [10], [11], [12]]
BIMONTHLY_RANGE = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12]]
QUARTERLY_RANGE = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]
BIANNUAL_RANGE = [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]
ANUAL_RANGE = [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]]


class WithholdingCertificates(models.TransientModel):
    _name = "withholding.certificates.wizard"
    _description = "Withholding certificates"

    company_id = fields.Many2one(
        'res.company', string="Company", required=True, default=lambda self: self.env.company)
    certificate_id = fields.Many2one(
        comodel_name='withholding.certificate.type', string="Withholding certificate type", required=True)
    certificate_period_id = fields.Many2one(
        comodel_name='certificate.period', string="Certificate period", required=True)
    periodicity = fields.Selection(
        string="Periodicity", required=True, related='certificate_period_id.periodicity')
    partner_ids = fields.Many2many(
        'res.partner', string="Partners", required=True)

    def create_certificates(self, avoid_void_lines=False):
        certificate_report = self.env['withholding.certificate.report']
        certificate_report_line = self.env['withholding.certificate.report.line']
        message, reports_to_create = self.generate_report_move_partner_lines(
            avoid_void_lines)
        if message != '':
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'withholding.certificates.wizard.confirm',
                'name': "Withholding certificate wizard confirm",
                'view_mode': 'form',
                'context': {
                    'default_wizard_id': self.id,
                    'default_description': message,
                    'default_company_id': self.company_id.id,
                    'default_certificate_id': self.certificate_id.id,
                    'default_certificate_period_id': self.certificate_period_id.id,
                    'default_periodicity': self.periodicity,
                    'default_partner_ids': [(6, 0, self.partner_ids.ids)]
                },
                'target': 'new',
            }
        else:
            report_ids = []
            for report_to_create in reports_to_create:
                report = certificate_report.create(report_to_create[0])
                for report_line in report_to_create[1]:
                    report_line['report_id'] = report.id
                    certificate_report_line.create(report_line)
                report_ids.append(report.id)
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'withholding.certificate.report',
                'name': "Withholding certificate reports",
                'view_mode': 'list,form',
                'domain': [('id', 'in', report_ids)],
                'target': 'current'
            }

    def generate_report_lines_vals(self, partner):
        report_lines = []
        account_move_line = self.env['account.move.line']
        if self.certificate_id.ica:
            date_ranges = self.get_date_ranges()
        else:
            date_ranges = [[self.certificate_period_id.date_from,
                            self.certificate_period_id.date_to]]
        for date_range in date_ranges:
            for line in self.certificate_id.line_ids:
                move_lines = account_move_line.search([
                    ('account_id', '=', line.tax_account.id),
                    ('tax_line_id', '=', line.tax.id),
                    ('company_id', '=', self.company_id.id),
                    ('partner_id', '=', partner.id),
                    ('date', '>=', date_range[0]),
                    ('date', '<=', date_range[1]),
                    ('parent_state', '=', 'posted')
                ])
                # Añadir los que estan en paid
                #
                total_amount = 0
                total_base_amount = 0
                move_line_qty = 0
                for m_line in move_lines:
                    total_amount += m_line.credit - m_line.debit
                    tax_base_amount = m_line.tax_base_amount if m_line.credit > 0 else - \
                        1*m_line.tax_base_amount
                    total_base_amount += tax_base_amount
                    move_line_qty += 1
                # if total_amount > 0:
                if total_amount > 0:
                    report_line = {
                        'tax_account': line.tax_account.id,
                        'tax_id': line.tax.id,
                        'base_amount': total_base_amount,
                        'amount_withheld': total_amount,
                        'percentage': abs(line.tax.amount),
                        'movements_qty': move_line_qty,
                        'period': str(date_range[0]) + ' - ' + str(date_range[1]),
                        'city_id': line.city_id.id
                    }
                    report_lines.append(report_line)
        return report_lines

    def get_date_ranges(self):
        periodicity = self.certificate_period_id.periodicity
        date_from = self.certificate_period_id.date_from
        date_to = self.certificate_period_id.date_to
        if periodicity == 'monthly':
            range = MONTHLY_RANGE
        elif periodicity == 'bimonthly':
            range = BIMONTHLY_RANGE
        elif periodicity == 'quarterly':
            range = QUARTERLY_RANGE
        elif periodicity == 'biannual':
            range = BIANNUAL_RANGE
        else:
            range = ANUAL_RANGE
        for span in range:
            if date_from.month in span:
                init_index = range.index(span)
            if date_to.month in span:
                end_index = range.index(span)
        range_list = range[init_index: end_index + 1]
        range_dates = []
        for line in range_list:
            init_date = date(date_from.year, line[0], date_from.day)
            last_day = calendar.monthrange(date_from.year, line[-1])[1]
            end_date = date(date_from.year, line[-1], last_day)
            range_dates.append([init_date, end_date])
        return range_dates

    def generate_report_move_partner_lines(self, avoid_void_lines):
        reports_to_create = []
        message = ''
        for partner in self.partner_ids:
            # Create report lines
            report_lines = self.generate_report_lines_vals(partner)
            message += self.eval_report_move_lines(report_lines, partner)
            report_vals = {
                'company_id': self.company_id.id,
                'certificate_id': self.certificate_id.id,
                'certificate_period_id': self.certificate_period_id.id,
                'periodicity': self.periodicity,
                'partner_id': partner.id,
            }
            if avoid_void_lines and message != '':
                message = ''
            else:
                reports_to_create.append([report_vals, report_lines])
        return message, reports_to_create

    def eval_report_move_lines(self, report_lines, partner):
        message = ''
        movements_qty = sum(report_line['movements_qty']
                            for report_line in report_lines)
        if movements_qty == 0:
            message = 'The partner %s do not contain move lines for the period \n' % (
                partner.display_name)
        return message


class WithholdingCertificatesConfirm(models.TransientModel):
    _name = "withholding.certificates.wizard.confirm"
    _description = "Withholding certificates confirm"

    wizard_id = fields.Many2one(
        'withholding.certificates.wizard', string="Wizard")
    description = fields.Text(string="Message:", default=False)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True)
    certificate_id = fields.Many2one(
        comodel_name='withholding.certificate.type', string="Withholding certificate type", required=True)
    certificate_period_id = fields.Many2one(
        comodel_name='certificate.period', string="Certificate period", required=True)
    periodicity = fields.Selection(
        string="Periodicity", required=True, related='certificate_period_id.periodicity')
    partner_ids = fields.Many2many(
        'res.partner', string="Partners", required=True)

    def action_confirm(self):
        return self.wizard_id.create_certificates(avoid_void_lines=True)

    def action_cancel(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'withholding.certificates.wizard',
            'name': "Withholding certificate wizard",
            'view_mode': 'form',
            'context': {
                'default_company_id': self.company_id.id,
                'default_certificate_id': self.certificate_id.id,
                'default_certificate_period_id': self.certificate_period_id.id,
                'default_periodicity': self.periodicity,
                'default_partner_ids': [(6, 0, self.partner_ids.ids)]
            },
            'target': 'new',
        }
