# -*- coding: utf-8 -*-

from datetime import datetime, time
from odoo import fields, models
import pytz


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

    def action_data(self):
        """
        Genera reportes de valuación de inventario con soporte para > 1M registros (v19: valor en stock.move, sin stock.valuation.layer).
        
        Retorna:
            tuple: (historic_totals dict, _yield_layers generator)
                - historic_totals: cantidades y valores anteriores a date_from
                - _yield_layers: generador que produce filas por lotes de 2000
        """
        self.ensure_one()
        lang = self.env.user.lang or 'es_CO'
        cr = self.env.cr
        params = {
            'lang': lang,
            'company_id': self.company_id.id
        }
        where = [
            "l.company_id = %(company_id)s",
            "pt.is_storable",
        ]
        # Cantidad valorada (igual que stock.move._get_valued_qty): líneas
        # pickeadas que entran/salen de ubicaciones valoradas (internal/transit
        # de una compañía), en UdM del producto.
        lateral_qty = (
            "LEFT JOIN LATERAL (SELECT COALESCE(SUM(ml.quantity_product_uom), 0.0) AS qty "
            "FROM stock_move_line ml "
            "JOIN stock_location lsrc ON lsrc.id = ml.location_id "
            "JOIN stock_location ldst ON ldst.id = ml.location_dest_id "
            "WHERE ml.move_id = sm.id AND ml.picked "
            "AND ((sm.is_in "
            "AND NOT (lsrc.company_id IS NOT NULL AND lsrc.usage IN ('internal','transit')) "
            "AND (ldst.company_id IS NOT NULL AND ldst.usage IN ('internal','transit'))) "
            "OR (sm.is_out "
            "AND (lsrc.company_id IS NOT NULL AND lsrc.usage IN ('internal','transit')) "
            "AND NOT (ldst.company_id IS NOT NULL AND ldst.usage IN ('internal','transit'))))"
            ") mq ON TRUE"
        )
        # Costos en destino (stock_landed_costs, opcional). En v18 cada costo
        # generaba una capa aparte (cantidad 0); en v19 se suma al valor del
        # movimiento, así que se separa en filas propias para conservar el
        # mismo detalle del reporte.
        cr.execute("SELECT to_regclass('stock_valuation_adjustment_lines') IS NOT NULL")
        has_landed = cr.fetchone()[0]
        if has_landed:
            lc_join = (
                "LEFT JOIN LATERAL (SELECT COALESCE(SUM(adj.additional_landed_cost), 0.0) AS total "
                "FROM stock_valuation_adjustment_lines adj "
                "JOIN stock_landed_cost lc ON lc.id = adj.cost_id AND lc.state = 'done' "
                "WHERE adj.move_id = sm.id) lct ON TRUE"
            )
            lc_total = "COALESCE(lct.total, 0.0)"
            lc_union = """
                UNION ALL
                SELECT sm.id, sm.company_id, GREATEST(sm.date, lc.write_date) AS date, sm.product_id,
                    sm.partner_id, sm.location_id, sm.location_dest_id, sm.reference, sm.origin,
                    1 AS kind, lc.name AS description, 0.0 AS qty,
                    CASE WHEN sm.is_in THEN adj.additional_landed_cost ELSE -adj.additional_landed_cost END AS value,
                    0.0 AS unit_cost
                FROM stock_valuation_adjustment_lines adj
                JOIN stock_landed_cost lc ON lc.id = adj.cost_id AND lc.state = 'done'
                JOIN stock_move sm ON sm.id = adj.move_id
                WHERE sm.state = 'done' AND (sm.is_in OR sm.is_out)
                    AND adj.additional_landed_cost != 0
            """
        else:
            lc_join = ""
            lc_total = "0.0"
            lc_union = ""
        layers_sql = f"""
            (
                SELECT sm.id, sm.company_id, sm.date, sm.product_id,
                    sm.partner_id, sm.location_id, sm.location_dest_id, sm.reference, sm.origin,
                    0 AS kind,
                    COALESCE(sm.reference, '') || COALESCE(' - ' || pvm.description, '') AS description,
                    CASE WHEN sm.is_in THEN mq.qty ELSE -mq.qty END AS qty,
                    CASE WHEN sm.is_in THEN sm.value - {lc_total} ELSE -(sm.value - {lc_total}) END AS value,
                    CASE WHEN mq.qty != 0 THEN (sm.value - {lc_total}) / mq.qty ELSE 0.0 END AS unit_cost
                FROM stock_move sm
                {lateral_qty}
                {lc_join}
                LEFT JOIN LATERAL (SELECT pv.description FROM product_value pv
                    WHERE pv.move_id = sm.id ORDER BY pv.date DESC, pv.id DESC LIMIT 1) pvm ON TRUE
                WHERE sm.state = 'done' AND (sm.is_in OR sm.is_out) AND sm.value != 0
                {lc_union}
            ) l
        """
        joins = [
            "JOIN product_product pp ON pp.id = l.product_id",
            "JOIN product_template pt ON pt.id = pp.product_tmpl_id",
            "LEFT JOIN product_category pc ON pc.id = pt.categ_id",
            "JOIN uom_uom u ON u.id = pt.uom_id",
            "LEFT JOIN res_partner rp ON rp.id = l.partner_id",
            "LEFT JOIN stock_location sl ON sl.id = l.location_id",
            "LEFT JOIN stock_location sl_dest ON sl_dest.id = l.location_dest_id",
        ]
        historic_joins = joins[:2]
        date_from = False
        date_to = False
        
        # Las fechas en BD están en UTC, pero el usuario selecciona en su zona horaria local
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        
        if self.date_from:
            # Combinamos fecha con 00:00:00 en la zona horaria del usuario
            date_from_naive = datetime.combine(self.date_from, time.min)
            date_from_user = user_tz.localize(date_from_naive)
            # Convertir a UTC para la comparación en BD
            date_from = date_from_user.astimezone(pytz.UTC)
        
        if self.date_to:
            # Combinar fecha con 23:59:59 en la zona horaria del usuario
            # para incluir todo el día
            date_to_naive = datetime.combine(self.date_to, time.max)
            date_to_user = user_tz.localize(date_to_naive)
            # Convertir a UTC para la comparación en BD
            date_to = date_to_user.astimezone(pytz.UTC)
            where.append("l.date <= %(date_to)s")
            params['date_to'] = date_to

        if self.categories_ids:
            where.append("pt.categ_id IN %(categories_ids)s")
            params['categories_ids'] = tuple(self.categories_ids.ids)

        if self.products_ids:
            where.append("l.product_id IN %(products_ids)s")
            params['products_ids'] = tuple(self.products_ids.ids)

        historic_totals = {}
        if date_from:
            historic_params = dict(params)
            historic_params['date_from'] = date_from
            historic_where = list(where) + ["l.date < %(date_from)s"]
            historic_sql = f"""
                SELECT
                    l.product_id,
                    COALESCE(SUM(l.qty), 0.0) AS quantity,
                    COALESCE(SUM(l.value), 0.0) AS value
                FROM {layers_sql}
                {' '.join(historic_joins)}
                WHERE {' AND '.join(historic_where)}
                GROUP BY l.product_id
            """
            cr.execute(historic_sql, historic_params)
            for row in cr.dictfetchall():
                historic_totals[row['product_id']] = {
                    'quantity': row['quantity'],
                    'value': row['value'],
                }

        if date_from:
            where.append("l.date >= %(date_from)s")
            params['date_from'] = date_from

        sql = f"""
            SELECT
                row_number() OVER (ORDER BY l.date, l.kind, l.id) AS seq,
                l.id,
                l.date AS create_date,
                l.description,
                l.product_id,
                COALESCE(pt.name->>%(lang)s, pt.name->>'en_US', '-') AS product_name,
                pp.default_code AS product_code,
                pc.name AS pc_name,
                l.qty AS quantity,
                pt.uom_id,
                COALESCE(u.name->>%(lang)s, u.name->>'en_US', '-') AS uom_name,
                l.unit_cost,
                l.value,
                l.id AS stock_move_id,
                l.reference AS sm_reference,
                l.origin AS sm_origin,
                rp.name AS rp_name,
                sl.complete_name AS loc_name,
                sl_dest.complete_name AS loc_dest_name
            FROM {layers_sql}
            {' '.join(joins)}
            WHERE {' AND '.join(where)}
            ORDER BY l.date, l.kind, l.id
        """
        batch_size = 2000
        if self.env.context.get('batch_size'):
            batch_size = self.env.context['batch_size'] or 2000

        def _yield_layers(batch_size=batch_size):
            cr.execute(sql, params)
            columns = [desc[0] for desc in cr.description]
            while True:
                rows = cr.fetchmany(batch_size)
                if not rows:
                    break
                for row in rows:
                    yield dict(zip(columns, row))

        return historic_totals, _yield_layers()
