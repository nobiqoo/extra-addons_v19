# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

import time as time_module
import logging
_logger = logging.getLogger(__name__)

move_types = {
    '1': 'Entrada',
    '-1': 'Salida',
    '0': 'Interna',
}


class StockMoveWizard(models.TransientModel):
    _name = 'stock.move.wizard'
    _description = 'Stock move wizard'

    def _default_company_id(self):
        return self.env.company

    def _default_user_id(self):
        return self.env.user

    categories_ids = fields.Many2many('product.category')

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=_default_company_id,
        required=True
    )

    date_start = fields.Date('Start date')
    date_end = fields.Date('End date')

    locations_ids = fields.Many2many('stock.location')

    products_ids = fields.Many2many('product.product')

    range_id = fields.Many2one('date.range')

    user_id = fields.Many2one(
        comodel_name='res.users',
        default=_default_user_id,
        required=True
    )

    warehouses_ids = fields.Many2many('stock.warehouse')

    @api.onchange('range_id')
    def _onchange_range_id(self):
        if self.range_id:
            self.date_start = self.range_id.date_start
            self.date_end = self.range_id.date_end

    def generate_report(self):
        self.ensure_one()
        data = None
        report_type = self.env.context.get('report_type') or 'xlsx'
        if report_type == 'xlsx':
            data = self.prepare_data()
            report_name = 'stock_report.report_stock_move_xlsx'
        if report_type == 'pdf':
            report_name = 'stock_report.action_report_stock_move_pdf'
        if report_type == 'html':
            report_name = 'stock_report.action_report_stock_move_html'
        report = self.env.ref(report_name)
        return report.report_action(self, data=data)

    def prepare_data(self):
        self.ensure_one()
        return {
            'record_id': self.id
        }

    def prepare_data_ok(self):
        self.ensure_one()
        time_start = time_module.perf_counter()
        Location = self.env['stock.location']
        Move = self.env['stock.move']
        Product = self.env['product.product']

        locations = self.locations_ids
        if not locations:
            domain = [
                ('usage', 'in', ['internal', 'transit']),
                '|',
                ('company_id', '=', self.company_id.id),
                ('company_id', '=', False)
            ]
            if self.warehouses_ids:
                domain.append(('warehouse_id', 'in', self.warehouses_ids.ids))
            locations = Location.search(domain)

        products = self.products_ids
        if not products:
            domain = [
                ('type', '=', 'consu'),
                '|',
                ('company_id', '=', self.company_id.id),
                ('company_id', '=', False)
            ]
            if self.categories_ids:
                domain.append(('categ_id', 'in', self.categories_ids.ids))
            products = Product.search(domain)

        date_end = fields.Date.add(self.date_end, days=1)
        move_data = []
        move_domain = [
            ('date', '>=', fields.Datetime.to_datetime(self.date_start)),
            ('date', '<=', fields.Datetime.to_datetime(date_end)),
            ('product_id', 'in', products.ids),
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            '|',
            ('location_id', 'in', locations.ids),
            ('location_dest_id', 'in', locations.ids)
        ]
        moves = Move.search(move_domain, order='date, id')
        to_date = fields.Date.subtract(self.date_start, days=1)
                
        out_locations = {}
        for move in moves:
            location = []
            if move.location_id.id == move.location_dest_id.id:
                move_type = 0
                location.append((move.location_id, move_type))
            else:
                if move.location_id.usage in ('internal', 'transit'):
                    move_type = -1
                    location.append((move.location_id, move_type))
                if move.location_dest_id.usage in ('internal', 'transit'):
                    move_type = 1
                    location.append((move.location_dest_id, move_type))
                # else:
                #     raise ValueError(_("Move does not involve an internal location: \n %s --> [%s] %s") % (move.picking_id.display_name, move.id, move.display_name))
            product = move.product_id
            # Define arreglo
            for loc_id, move_type in location:
                if str(loc_id.id) not in out_locations:
                    out_locations[str(loc_id.id)] = {
                        'id': loc_id.id,
                        'name': loc_id.complete_name,
                        'products': {}
                    }
                if str(product.id) not in out_locations[str(loc_id.id)]['products']:
                    qty_available = product.with_context(
                        location=loc_id.id,
                        to_date=to_date,
                        allowed_company_ids=[self.company_id.id],
                    ).qty_available
                    out_locations[str(loc_id.id)]['products'][str(product.id)] = {
                        'id': product.id,
                        'name': product.display_name,
                        'qty_available': qty_available,
                        'moves': []
                    }
                # Qty
                qty = move.product_uom_qty * move_type

            # Price
                price_unit = move._get_price_unit() 
                price_total = price_unit * qty
                qty_available = out_locations[str(loc_id.id)]['products'][str(product.id)]['qty_available']
                move_vals = {
                    'id': move.id,
                    'date': move.date,
                    'reference': move.reference,
                    'origin': move.origin or '',
                    'partner': move.partner_id and move.partner_id.display_name or '',
                    'product': move.product_id.display_name,
                    'from': move.location_id.complete_name,
                    'to': move.location_dest_id.complete_name,
                    'type': move_types.get(str(move_type)),
                    # 'init': svl_quantity,
                    'init': qty_available,
                    # 'demand': move.product_uom_qty,
                    'demand': move.quantity,
                    # 'final': svl_quantity + qty,
                    'final': qty_available + qty,
                    'uom': move.product_uom.name,
                    'unit': price_unit,
                    'total': price_total,
                    'company': move.company_id.name,
                    'status': _(move.state),
                }
                out_locations[str(loc_id.id)]['products'][str(product.id)]['moves'].append(move_vals)
                out_locations[str(loc_id.id)]['products'][str(product.id)]['qty_available'] += qty

        time_end = time_module.perf_counter()
        _logger.warning(f"KARDEX: Data prepared in {time_end - time_start:.2f} seconds")
        return {
            'company': self.company_id.name,
            'user': self.env.user.name,
            'start': self.date_start,
            'end': self.date_end,
            # 'products': product_data,
            'locations': list(out_locations.values())
        }

    def report_data(self):
        return self.prepare_data()
