# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class PurchaseOrderReport(models.Model):
    _name = 'purchase.import.report'
    _description = 'Purchase Order Report'
    _order = 'order_name desc'
    _auto = False

    order_name = fields.Char()
    product_id = fields.Many2one('product.product')
    ordered_qty = fields.Float()
    received_qty = fields.Float()
    qty_to_receive = fields.Float()
    product_code = fields.Char()
    product_name = fields.Char(translate=True)
    product_description = fields.Html(translate=True)
    product_category = fields.Many2one('product.category')
    product_brand = fields.Char()
    purchase_order_id = fields.Many2one('purchase.order')
    order_subtotal = fields.Float()
    purchase_order_currency_id = fields.Many2one('res.currency')
    order_status = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ])
    planned_date = fields.Date('Planned Date')
    term_and_conditions = fields.Html()
    picking_type_id = fields.Many2one('stock.picking.type')
    import_name = fields.Char()
    date_origin = fields.Date()
    date_port = fields.Date()
    date_destination = fields.Date()
    type = fields.Selection([
        ('International', 'International'),
        ('National', 'National'),
    ])

    def _auto_init(self):

        tools.drop_view_if_exists(self._cr, 'purchase_import_report')
        self._cr.execute("DROP TABLE IF EXISTS purchase_import_report;")
        self._cr.execute("DROP VIEW IF EXISTS purchase_import_report;")

        self._cr.execute("""
            CREATE OR REPLACE VIEW purchase_import_report AS (
                WITH valid_orders AS (
                    SELECT
                        po.name AS order_name
                    FROM
                        purchase_order po
                    LEFT JOIN
                        stock_picking sp ON po.name = sp.origin
                    WHERE
                        po.state = 'draft' AND sp.id IS NULL
                    UNION
                    SELECT
                        sp.origin
                    FROM
                        stock_picking sp
                    GROUP BY
                        sp.origin
                    HAVING
                        SUM(CASE WHEN sp.state NOT IN ('draft', 'done', 'cancel') THEN 1 ELSE 0 END) > 0
                ),
                pickings_done AS (
                    SELECT
                        sp.origin,
                        sm.product_id,
                        SUM(sml.quantity) AS total_quantity_done
                    FROM
                        stock_picking sp
                    JOIN
                        stock_move sm ON sp.id = sm.picking_id
                    JOIN
                        stock_move_line sml ON sm.id = sml.move_id
                    WHERE
                        sp.state = 'done'
                    GROUP BY
                        sp.origin, sm.product_id
                )
                SELECT
                    row_number() OVER () As id,
                    po.name AS order_name,
                    pp.id AS product_id,
                    pol.product_uom_qty AS ordered_qty,
                    COALESCE(pd.total_quantity_done, 0) AS received_qty,
                    pol.product_uom_qty - COALESCE(pd.total_quantity_done, 0) AS qty_to_receive,
                    pp.default_code AS product_code,
                    pt.name AS product_name,
                    pt.description AS product_description,
                    pt.categ_id AS product_category,
                    pb.name AS product_brand,
                    po.id AS purchase_order_id,
                    pol.price_subtotal AS order_subtotal,
                    po.currency_id AS purchase_order_currency_id,
                    po.state AS order_status,
                    po.date_planned AS planned_date,
                    po.note AS term_and_conditions,
                    po.picking_type_id AS picking_type_id,
                    pi.name AS import_name,
                    pi.date_origin AS date_origin,
                    pi.date_port AS date_port,
                    pi.date_destination AS date_destination,
                    CASE
                        WHEN
                            pi.name IS NOT NULL OR rc.name != 'COP'
                        THEN
                            'International'
                        ELSE
                            'National'
                    END AS type
                FROM
                    purchase_order AS po
                INNER JOIN
                    purchase_order_line pol ON po.id = pol.order_id
                LEFT JOIN
                    purchase_import_purchase_order_rel rel ON po.id = rel.purchase_order_id
                LEFT JOIN
                    purchase_import pi ON rel.purchase_import_id = pi.id
                INNER JOIN
                    product_product pp ON pol.product_id = pp.id
                LEFT JOIN
                    pickings_done pd ON po.name = pd.origin AND pp.id = pd.product_id
                INNER JOIN
                    product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN
                    product_brand pb ON pt.product_brand_id = pb.id
                LEFT JOIN
                    res_currency rc ON po.currency_id = rc.id
                WHERE
                    po.name IN (SELECT order_name FROM valid_orders)
                AND
                    po.state NOT IN ('done', 'cancel')
                AND
                    (pi.state IS NULL OR pi.state != 'cancel')
                GROUP BY
                    po.id,
                    pp.id,
                    pt.id,
                    pb.id,
                    pol.id,
                    pi.id,
                    pd.total_quantity_done,
                    rc.id
            );
        """)
