# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import UserError


class SaleOrderReportWizard(models.TransientModel):
    _name = 'sale.order.report.wizard'
    _description = 'Sale Order Report Wizard'

    partner_id = fields.Many2one('res.partner', string='Customer')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    category_id = fields.Many2one('product.category', string='Categories')
    product_id = fields.Many2one('product.product')

    def button_generate_report(self):
        sale_order_report = self.env['sale.order.report']

        partner_id = self.partner_id.id if self.partner_id else None
        start_date = self.start_date
        end_date = self.end_date
        if end_date < start_date:
            raise UserError(
                _("The end date cannot be less than the start date."))
        category_id = self.category_id.id if self.category_id else None
        product_id = self.product_id.id if self.product_id else None

        return sale_order_report.generate_report(start_date, end_date, partner_id, category_id, product_id)
