# -*- coding: utf-8 -*-

from odoo import fields, models


class StockValuationReport(models.TransientModel):
    _name = 'stock.valuation.report'
    _description = 'Stock Valuation Report'

    categories_ids = fields.Many2many('product.category')

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company
    )

    date_from = fields.Date()
    date_to = fields.Date()

    products_ids = fields.Many2many('product.product')
    # locations_ids = fields.Many2many('stock.location')

    def action_report(self):
        report = self.env.ref(
            'stock_report.action_report_stock_valuation_report')
        return report.report_action(self)

    def ation_data(self):
        self.ensure_one()
        Move = self.env['stock.move']
        layer_domain = [
            ('company_id', '=', self.company_id.id),
            ('product_id.is_storable', '=', True),
            ('state', '=', 'done'),
            ('value', '!=', 0),
        ]
        blayer_domain = layer_domain.copy()
        if self.date_from:
            layer_domain.append(
                ('date', '>=', fields.Datetime.to_datetime(self.date_from)))
            blayer_domain.append(
                ('date', '<', fields.Datetime.to_datetime(self.date_from)))
        if self.date_to:
            date_to = fields.Date.add(self.date_to, days=1)
            layer_domain.append(
                ('date', '<=', fields.Datetime.to_datetime(date_to)))
        if self.categories_ids:
            layer_domain.append(
                ('product_id.categ_id', 'in', self.categories_ids.ids))
            blayer_domain.append(
                ('product_id.categ_id', 'in', self.categories_ids.ids))
        if self.products_ids:
            layer_domain.append(('product_id', 'in', self.products_ids.ids))
            blayer_domain.append(('product_id', 'in', self.products_ids.ids))
        layer_fields = [
            'date',
            'value_justification',
            'product_id',
            'quantity',
            'remaining_qty',
            'product_uom',
            'value',
            'account_move_id',
        ]
        layer_order = 'date, id'
        layers = Move.search_read(
            domain=layer_domain, fields=layer_fields, order=layer_order)

        if self.date_from:
            blayers = Move.search_read(
                domain=blayer_domain, fields=layer_fields, order=layer_order)
            return blayers, layers
        else:
            return [], layers
