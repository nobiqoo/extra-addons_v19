# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools


class PurchaseOrderSimpleReport(models.Model):
    _name = 'purchase.import.simple.report'
    _description = 'Simplified Purchase Order Report'
    _order = 'order_name desc'
    _auto = False

    order_name = fields.Char()
    import_name = fields.Char()
    product_category = fields.Many2one('product.category')
    order_subtotal = fields.Float()
    date_origin = fields.Date()
    date_port = fields.Date()
    date_destination = fields.Date()

    def _auto_init(self):

        tools.drop_view_if_exists(self._cr, 'purchase_import_simple_report')
        self._cr.execute("DROP TABLE IF EXISTS purchase_import_simple_report;")
        self._cr.execute("DROP VIEW IF EXISTS purchase_import_simple_report;")

        self._cr.execute("""
            CREATE OR REPLACE VIEW purchase_import_simple_report AS (
                WITH valid_orders AS (
                    SELECT
                        po.name AS order_name
                    FROM
                        purchase_order po
                        LEFT JOIN stock_picking sp ON po.name = sp.origin
                    WHERE
                        po.state = 'draft'
                        AND sp.id IS NULL
                    UNION
                    SELECT
                        sp.origin
                    FROM
                        stock_picking sp
                    GROUP BY
                        sp.origin
                    HAVING
                        SUM(
                            CASE
                                WHEN sp.state NOT IN ('draft', 'done', 'cancel') THEN 1
                                ELSE 0
                            END
                        ) > 0
                )
                SELECT
                    row_number() OVER () As id,
                    po.name AS order_name,
                    pi.name AS import_name,
                    pt.categ_id AS product_category,
                    SUM(pol.price_subtotal) AS order_subtotal,
                    pi.date_origin AS date_origin,
                    pi.date_port AS date_port,
                    pi.date_destination AS date_destination
                FROM
                    purchase_order AS po
                    INNER JOIN purchase_order_line pol ON po.id = pol.order_id
                    LEFT JOIN purchase_import_purchase_order_rel rel ON po.id = rel.purchase_order_id
                    LEFT JOIN purchase_import pi ON rel.purchase_import_id = pi.id
                    INNER JOIN product_product pp ON pol.product_id = pp.id
                    INNER JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    LEFT JOIN res_currency rc ON po.currency_id = rc.id
                WHERE
                    po.name IN (
                        SELECT
                            order_name
                        FROM
                            valid_orders
                    )
                    AND po.state NOT IN ('done', 'cancel')
                    AND rc.name != 'COP'
                    AND (pi.state IS NULL OR pi.state != 'cancel')
                GROUP BY
                    po.name,
                    pt.categ_id,
                    pi.name,
                    pi.date_origin,
                    pi.date_port,
                    pi.date_destination
                ORDER BY
                    po.name
            );
        """)
