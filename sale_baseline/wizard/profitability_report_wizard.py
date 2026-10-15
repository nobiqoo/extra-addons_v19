# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import UserError


class ProfitabilityReportWizard(models.TransientModel):
    _name = 'profitability.report.wizard'
    _description = 'Profitability Report Wizard'

    partner_id = fields.Many2one('res.partner', string='Customer')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    category_id = fields.Many2one('product.category', string='Categories')
    product_id = fields.Many2one('product.product')
    services_included = fields.Boolean(
        string='Include Services', default=False, help="Check this box to include services in the report. Uncheck to exclude them.")

    def button_generate_report(self):
        profitability_report = self.env['profitability.report']

        partner_id = self.partner_id.id if self.partner_id else None
        start_date = self.start_date
        end_date = self.end_date
        if end_date < start_date:
            raise UserError(
                _("The end date cannot be less than the start date."))
        category_id = self.category_id.id if self.category_id else None
        product_id = self.product_id.id if self.product_id else None
        services_included = self.services_included

        return profitability_report.generate_report(start_date, end_date, services_included, partner_id, category_id, product_id)
