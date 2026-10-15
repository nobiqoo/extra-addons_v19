# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import UserError


class InventoryTurnoverAnalysisWizard(models.TransientModel):
    _name = 'inventory.turnover.analysis.wizard'
    _description = 'Inventory Turnover Analysis Wizard'

    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    category_ids = fields.Many2many('product.category', string='Category')
    product_ids = fields.Many2many('product.product', string="Product", domain=[('product_tmpl_id.type', '=', 'consu')])
    warehouse_ids = fields.Many2many('stock.warehouse', string="Warehouse")

    def button_generate_report(self):
        inventory_turnover_analysis = self.env['inventory.turnover.analysis']

        start_date = self.start_date
        end_date = self.end_date
        if end_date < start_date:
            raise UserError(
                _("The end date cannot be less than the start date."))
        product_ids = self.product_ids.ids if self.product_ids else None
        category_ids = self.category_ids.ids if self.category_ids else None
        warehouse_ids = self.warehouse_ids.ids if self.warehouse_ids else None

        return inventory_turnover_analysis.generate_report(start_date, end_date, product_ids, category_ids, warehouse_ids)
