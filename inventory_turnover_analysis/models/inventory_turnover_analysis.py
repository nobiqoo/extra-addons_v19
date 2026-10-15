# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
import pytz


class InventoryTurnoverAnalysis(models.Model):
    _name = 'inventory.turnover.analysis'
    _description = 'Inventory turnover analysis'
    
  
    product_id = fields.Many2one('product.product', 'Product')
    category_id = fields.Many2one('product.category', 'Category')
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse')
    company_id = fields.Many2one('res.company', 'Company')
    qty_on_hand = fields.Float('Quantity on hand')
    qty_sold = fields.Float('Quantity sold')
    last_receipt_date = fields.Date('Last receipt date')
    last_receipt_ref = fields.Char('Last receipt reference')
    
    def _get_dates_utc(self,start_date,end_date):
        tz_name = self.env.user.tz or 'UTC'
        tz = pytz.timezone(tz_name)
        
        start_date = datetime.combine(start_date, datetime.min.time())
        end_date = datetime.combine(end_date, datetime.max.time())
        
        # Convert to UTC according with user's zone
        start_utc = tz.localize(start_date).astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = tz.localize(end_date).astimezone(pytz.utc).replace(tzinfo=None)
        
        return start_utc, end_utc

    @api.model
    def get_report_data(self, start_date, end_date, product_ids=None,category_ids=None, warehouse_ids=None):
        start_date_utc, end_date_utc = self._get_dates_utc(start_date,end_date)
        company_ids = tuple(self.env.companies.ids)
        query = """
            WITH
            -- qty on hand per warehouse
            stock_onhand AS (
                SELECT
                    sq.product_id,
                    sw.id AS warehouse_id,
                    sw.name AS warehouse_name,
                    sw.company_id AS company_id,
                    SUM(sq.quantity) AS qty_on_hand
                FROM stock_quant sq
                JOIN stock_location sl ON sl.id = sq.location_id
                JOIN stock_warehouse sw ON sl.complete_name LIKE sw.code ||  '/%%'
                    AND sl.company_id = sw.company_id   -- << avoid cross-company code collisions
                WHERE sl.usage = 'internal'
                AND sl.active = TRUE
                AND sw.company_id in %s   -- << selected companies
                GROUP BY sq.product_id, sw.id, sw.name, sw.company_id
            ),

            -- Sales according with filters dates.
            sales_period AS (
                SELECT
                    sol.product_id,
                    sw.id AS warehouse_id,
                    SUM(sol.product_uom_qty) AS qty_sold,
                    SUM(sol.price_subtotal) AS amount_sold
                FROM sale_order_line sol
                JOIN sale_order so ON so.id = sol.order_id
                JOIN stock_warehouse sw ON sw.id = so.warehouse_id
                WHERE so.state IN ('sale', 'done')
                AND so.date_order >= %s   -- << start_date
                AND so.date_order <=  %s   -- << end_date
                AND sw.company_id in %s   -- << selected companies
                GROUP BY sol.product_id, sw.id
            ),

            -- Last reception (date)
            last_receipt AS (
                SELECT DISTINCT ON (sm.product_id, sw.id)
                    sm.product_id,
                    sw.id AS warehouse_id,
                    sm.date AS last_receipt_date,
                    sp.name AS last_receipt_ref
                FROM stock_move sm
                JOIN stock_picking sp ON sp.id = sm.picking_id
                JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
                JOIN stock_location dest ON dest.id = sm.location_dest_id
                JOIN stock_warehouse sw ON dest.complete_name LIKE sw.code || '/%%'
                    AND dest.company_id = sw.company_id   -- << avoid cross-company code collisions
                WHERE sm.state = 'done'
                AND dest.usage = 'internal'
                AND spt.code = 'incoming'
                AND sw.company_id in %s   -- << selected companies
                ORDER BY sm.product_id, sw.id, sm.date DESC
            )

            -- Final join
            SELECT
                pp.id AS product_id,
                soh.warehouse_id,
                soh.company_id,
                COALESCE(soh.qty_on_hand, 0) AS qty_on_hand,
                COALESCE(sp.qty_sold, 0) AS qty_sold,
                lr.last_receipt_date,
                lr.last_receipt_ref
            FROM product_product pp
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            LEFT JOIN product_category pc ON pc.id = pt.categ_id
            LEFT JOIN stock_onhand soh ON soh.product_id = pp.id
            LEFT JOIN sales_period sp ON sp.product_id = pp.id AND sp.warehouse_id = soh.warehouse_id
            LEFT JOIN last_receipt lr ON lr.product_id = pp.id AND lr.warehouse_id = soh.warehouse_id
            WHERE pt.type = 'consu'
            AND pt.active = TRUE
            AND pp.active = TRUE
            AND (pt.company_id IS NULL OR pt.company_id in %s)   -- << selected companies

        """
        params = [company_ids, start_date_utc, end_date_utc, company_ids, company_ids, company_ids]


        if product_ids:
            query += " AND pp.id in %s"
            params.append(tuple(product_ids))
            
        if category_ids:
            query += " AND pc.id in %s"
            params.append(tuple(category_ids))
        
        if warehouse_ids:
            query += " AND soh.warehouse_id in %s"
            params.append(tuple(warehouse_ids))
        
        if not product_ids and not category_ids and not warehouse_ids:
            query += " AND (qty_on_hand >0 OR qty_sold>0 or last_receipt_date is NOT NULL or last_receipt_ref is NOT NULL)"

        query += " ORDER BY soh.warehouse_id, pt.name;"

        self.env.cr.execute(query, tuple(params))

        result = self.env.cr.dictfetchall()
        if not result:
            raise UserError(_("No data, try again"))
        else:
            for line in result:
                self.create(line)
        
    @api.model
    def generate_report(self, start_date, end_date,product_ids=None,category_ids=None, warehouse_ids=None):
        self.search([('company_id', 'in', self.env.companies.ids + [False])]).unlink()
        self.get_report_data(start_date, end_date,product_ids,category_ids, warehouse_ids)

        return {
            'name': _('Inventory turnover analysis'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,pivot',
            'res_model': 'inventory.turnover.analysis',
            'target': 'current',
            'domain': [],
            'context': {},
        }
