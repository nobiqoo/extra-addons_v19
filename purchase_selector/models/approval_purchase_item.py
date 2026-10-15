from odoo import fields, models, tools

class ApprovalPurchaseItem(models.Model):
    _name = "approval.purchase.item"
    _description = "Ítems aprobados pendientes por comprar (consolidado)"
    _auto = False
    _order = "request_date desc, request_name, id"

    line_id = fields.Integer("ID línea REQ", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", default=lambda s: s.env.company, required=True)
    request_id = fields.Many2one("approval.request", "Requerimiento", readonly=True)
    request_name = fields.Char("N° Requerimiento", readonly=True)
    request_owner_id = fields.Many2one("res.users", "Solicitante", readonly=True)
    project_id = fields.Many2one("project.project", "Proyecto", readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", "Almacén", readonly=True)

    product_id = fields.Many2one("product.product", "Producto", readonly=True)
    description = fields.Char("Descripción", readonly=True)
    uom_id = fields.Many2one("uom.uom", "Unidad de medida", readonly=True)

    qty_approved = fields.Float("Cantidad aprobada", readonly=True, digits="Product Unit of Measure")
    qty_purchased = fields.Float("Cantidad comprada", readonly=True, digits="Product Unit of Measure")
    qty_to_buy = fields.Float("Cantidad", readonly=True, digits="Product Unit of Measure")
    qty_on_hand = fields.Float("A la mano", readonly=True, digits="Product Unit of Measure")

    request_date = fields.Date("Fecha sol.", readonly=True)
    vendor_id = fields.Many2one("res.partner", "Proveedor", readonly=True)
    managed_qty = fields.Float("Cantidad Gestionada", readonly=True, digits="Product Unit of Measure", help="Cantidad ya comprada/gestionada para esta línea.")
    qty_pending_purchase = fields.Float("Cantidad pendiente por comprar", readonly=True, digits="Product Unit of Measure", help="Resta entre la cantidad aprobada y la cantidad gestionada (nunca negativa).")

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'approval_product_line'
              AND column_name = 'warehouse_id'
            LIMIT 1
        """)
        has_apl_warehouse = bool(self._cr.fetchone())
        warehouse_select = "apl.warehouse_id" if has_apl_warehouse else "NULL::integer"
        self._cr.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'approval_request'
              AND column_name = 'project_id'
            LIMIT 1
        """)
        has_ar_project = bool(self._cr.fetchone())
        project_select = "ar.project_id" if has_ar_project else "NULL::integer"
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT
                apl.id                              AS id,
                apl.id                              AS line_id,
                ar.id                               AS request_id,
                ar.name                             AS request_name,
                ar.request_owner_id                 AS request_owner_id,
                ar.company_id                       AS company_id,
                {project_select}                    AS project_id,
                {warehouse_select}                  AS warehouse_id,
                apl.product_id                      AS product_id,
                apl.description                     AS description,
                apl.product_uom_id                  AS uom_id,

                COALESCE(apl.quantity, 0)::numeric  AS qty_approved,

                -- SUMA de TODAS las POL enlazadas por approval_line_id (excluye OCs canceladas)
                COALESCE(pol_sum.managed_qty, 0)::numeric AS managed_qty,

                -- compat: 'comprada' = gestionada
                COALESCE(pol_sum.managed_qty, 0)::numeric AS qty_purchased,

                -- Pendiente por comprar = aprobada - gestionada (>= 0)
                GREATEST(
                    COALESCE(apl.quantity,0)::numeric - COALESCE(pol_sum.managed_qty,0)::numeric - COALESCE(mv_sum.moved_qty,0)::numeric,
                    0::numeric
                ) AS qty_pending_purchase,

                -- (si mantienes qty_to_buy, que sea igual al pendiente)
                GREATEST(
                    COALESCE(apl.quantity,0)::numeric - COALESCE(pol_sum.managed_qty,0)::numeric - COALESCE(mv_sum.moved_qty,0)::numeric,
                    0::numeric
                ) AS qty_to_buy,

                COALESCE(st.qty_on_hand, 0)         AS qty_on_hand,
                ar.create_date::date                AS request_date,
                COALESCE(rp_seller.id, rp_vend.id)  AS vendor_id

            FROM approval_product_line apl
            JOIN approval_request ar ON ar.id = apl.approval_request_id

            LEFT JOIN (
                SELECT pol.approval_line_id AS apl_id,
                    SUM(pol.product_qty)::numeric AS managed_qty
                FROM purchase_order_line pol
                JOIN purchase_order po ON po.id = pol.order_id
                WHERE pol.approval_line_id IS NOT NULL
                AND po.state != 'cancel'
                GROUP BY pol.approval_line_id
            ) pol_sum ON pol_sum.apl_id = apl.id

            LEFT JOIN (
                SELECT sm.approval_line_id AS apl_id,
                    SUM(sm.product_uom_qty)::numeric AS moved_qty
                FROM stock_move sm
                LEFT JOIN stock_picking sp ON sp.id = sm.picking_id
                WHERE sm.approval_line_id IS NOT NULL
                  AND COALESCE(sp.state, sm.state) != 'cancel'
                GROUP BY sm.approval_line_id
            ) mv_sum ON mv_sum.apl_id = apl.id

            LEFT JOIN (
                SELECT
                    sq.product_id,
                    COALESCE(sq.company_id, sl.company_id) AS company_id,
                    SUM(sq.quantity)::numeric                         AS qty_on_hand
                FROM stock_quant sq
                JOIN stock_location sl ON sl.id = sq.location_id
                WHERE sl.usage = 'internal'
                  AND sq.owner_id IS NULL
                GROUP BY sq.product_id, COALESCE(sq.company_id, sl.company_id)
            ) st
              ON st.product_id = apl.product_id
             AND (
                   st.company_id = ar.company_id
                OR st.company_id IS NULL
                OR ar.company_id IS NULL
             )

            LEFT JOIN LATERAL (
                SELECT psi.partner_id AS vendor_id
                FROM product_supplierinfo psi
                JOIN product_product  pp ON pp.id = apl.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE
                    (psi.product_id = pp.id OR (psi.product_id IS NULL AND psi.product_tmpl_id = pt.id))
                    AND (psi.company_id IS NULL OR psi.company_id = ar.company_id)
                ORDER BY
                    CASE WHEN psi.product_id = pp.id THEN 0 ELSE 1 END,
                    COALESCE(psi.sequence, 0), psi.id
                LIMIT 1
            ) vend ON TRUE

            LEFT JOIN res_partner rp_seller
                ON rp_seller.id = apl.seller_id

            LEFT JOIN res_partner rp_vend
                ON rp_vend.id = vend.vendor_id

            WHERE GREATEST(
                COALESCE(apl.quantity,0)::numeric - COALESCE(pol_sum.managed_qty,0)::numeric - COALESCE(mv_sum.moved_qty,0)::numeric,
                0::numeric
            ) > 0
            AND ar.request_status NOT IN ('new','pending','refused','cancel','created_po','abastecido')
        """)
