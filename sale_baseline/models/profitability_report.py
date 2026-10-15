# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProfitabilityReport(models.Model):
    _name = 'profitability.report'
    _description = 'Profitability by Product Report'

    move_line_id = fields.Many2one('account.move.line', 'Move Line')
    date = fields.Date('Date')
    order_name = fields.Char('Sale Order')
    invoice_name = fields.Char('Invoice Name')
    refund_name = fields.Char('Refund Name')
    refund_for_high_value = fields.Char('Refund for High Value')
    analytic_distribution = fields.Char('Analytic Distribution')
    analytic_distribution_display = fields.Char('Cuenta Analítica')
    user_id = fields.Many2one('res.users', 'Salesperson')
    partner_id = fields.Many2one('res.partner', 'Partner')
    product_id = fields.Many2one('product.product', 'Product')
    category_id = fields.Many2one('product.category', 'Category')
    picking = fields.Char('Picking')
    detailed_type = fields.Selection([
        ('consu', 'Consumable'),
        ('service', 'Service'),
        ('combo', 'Combo'),])
    quantity_invoiced = fields.Float('Quantity Invoiced')
    weight = fields.Float('Weight')
    total_weight = fields.Float('Total Weight')
    unit_cost = fields.Float('Cost')
    total_cost = fields.Float('Total')
    sale_price = fields.Float('Sale Price')
    sale_price_total = fields.Float('Sale Price Total')
    margin = fields.Float('Margin')
    percentage = fields.Float('Percentage')

    @api.model
    def get_report_data(self, start_date, end_date, services_included, partner_id=None, category_id=None, product_id=None):
        query = """
            SELECT
                aml.id AS move_line_id,
                am.date AS date,
                so.name AS order_name,
                CASE
                    WHEN am.move_type = 'out_invoice' THEN am.name
                END AS invoice_name,
                CASE
                    WHEN am.move_type = 'out_refund' THEN am.name
                    ELSE NULL
                END AS refund_name,
                aml.analytic_distribution AS analytic_distribution,
                am.invoice_user_id AS user_id,
                rp.id AS partner_id,
                pp.id AS product_id,
                pc.id AS category_id,
                sp.name AS picking,
                pt.type AS detailed_type,
                CASE
                    WHEN am.move_type = 'out_refund' THEN ABS(aml.quantity) * (-1)
                    ELSE aml.quantity
                END AS quantity_invoiced,
                pp.weight AS weight,
               CASE
                    WHEN aml.product_uom_id = pt.uom_id
                        THEN aml.quantity
                    WHEN pp.weight IS NOT NULL AND pp.weight > 0
                        THEN aml.quantity * pp.weight
                    ELSE 0
                END AS total_weight,
                CASE
                    WHEN am.move_type = 'out_refund' THEN ABS(COALESCE(mv_cost.unit_cost, 0)) * (-1)
                    ELSE COALESCE(mv_cost.unit_cost, 0)
                END AS unit_cost,
                CASE
                    WHEN am.move_type = 'out_refund' THEN COALESCE(mv_cost.unit_cost, 0) * aml.quantity * (-1)
                    ELSE COALESCE(mv_cost.unit_cost, 0) * aml.quantity
                END AS total_cost,
                CASE
                    WHEN am.move_type = 'out_refund' THEN ABS(aml.price_unit*am.current_exchange_rate) * (-1)
                    ELSE aml.price_unit*am.current_exchange_rate
                END AS sale_price,
                CASE
                    WHEN am.move_type = 'out_refund' THEN ABS(aml.price_subtotal*am.current_exchange_rate) * (-1)
                    ELSE aml.price_subtotal*am.current_exchange_rate
                END AS sale_price_total,
                ABS(aml.price_subtotal*am.current_exchange_rate) - (
                    ABS(COALESCE(mv_cost.unit_cost, 0)) * aml.quantity
                ) AS margin,
                (
                    ABS(aml.price_subtotal*am.current_exchange_rate) - (
                        ABS(COALESCE(mv_cost.unit_cost, 0)) * aml.quantity
                    )
                ) / NULLIF(ABS(aml.price_subtotal*am.current_exchange_rate), 0) AS percentage
            FROM
                account_move am
                JOIN account_move_line aml ON aml.move_id = am.id
                JOIN res_partner rp ON am.partner_id = rp.id
                JOIN product_product pp ON aml.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_category pc ON pt.categ_id = pc.id
                LEFT JOIN uom_uom uom ON uom.id = aml.product_uom_id
                JOIN account_account aa ON aa.id = aml.account_id
                LEFT JOIN (
                    SELECT
                        invoice_line_id,
                        MIN(order_line_id) AS order_line_id
                    FROM
                        sale_order_line_invoice_rel
                    GROUP BY
                        invoice_line_id
                ) sol_map ON sol_map.invoice_line_id = aml.id
                LEFT JOIN sale_order_line sol_line ON sol_line.id = sol_map.order_line_id
                LEFT JOIN sale_order so ON so.id = sol_line.order_id
                LEFT JOIN (
                    SELECT
                        sm.sale_line_id,
                        MIN(sp.name) AS name
                    FROM
                        stock_move sm
                        JOIN stock_picking sp ON sp.id = sm.picking_id
                        JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
                    WHERE
                        sm.state = 'done'
                        AND (spt.code = 'outgoing' or spt.code = 'dropship')
                    GROUP BY
                        sm.sale_line_id
                ) sp ON sp.sale_line_id = sol_line.id
                LEFT JOIN (
                    SELECT
                        sm.sale_line_id,
                        sm.product_id,
                    CASE
                        WHEN SUM(
                            CASE
                                WHEN sml.picked THEN ABS(sml.quantity)
                                ELSE 0
                            END
                        ) <> 0
                        THEN SUM(ABS(sm.value)) /
                            NULLIF(
                                SUM(
                                    CASE
                                        WHEN sml.picked THEN ABS(sml.quantity)
                                        ELSE 0
                                    END
                                ),
                                0
                            )
                        ELSE 0
                    END AS unit_cost
                FROM stock_move sm
                JOIN stock_move_line sml ON sml.move_id = sm.id
                WHERE sm.state = 'done'
                GROUP BY
                    sm.sale_line_id,
                    sm.product_id
                ) mv_cost ON mv_cost.sale_line_id = sol_line.id
                AND mv_cost.product_id = pp.id
            WHERE
                am.move_type IN ('out_invoice', 'out_refund')
                AND am.state = 'posted'
                AND aml.product_id IS NOT NULL
                AND (
                    (am.move_type = 'out_invoice' AND so.name IS NOT NULL)
                    OR
                    (am.move_type = 'out_refund' AND am.name IS NOT NULL)
                )
                AND am.date >= %s
                AND am.date <= %s
                AND am.company_id = %s
        """

        params = [start_date, end_date, self.env.company.id]

        if partner_id:
            query += " AND rp.id = %s"
            params.append(partner_id)
        if category_id:
            query += " AND pc.id = %s"
            params.append(category_id)
        if product_id:
            query += " AND pp.id = %s"
            params.append(product_id)

        query += " ORDER BY aml.id"

        self.env.cr.execute(query, tuple(params))

        result = self.env.cr.dictfetchall()
        if not result:
            raise UserError(_("No data, try again"))
        processed_data = self.process_filter_data(result, services_included)

        for line in processed_data:
            if not services_included and line['detailed_type'] == 'service':
                continue
            else:
                self.create(line)

    @api.model
    def process_filter_data(self, data, services_included):
        analytic_accounts = self.env['account.analytic.account'].search([])
        account_dict = {
            str(account.id): account.name for account in analytic_accounts}
        for row in data:

            if row.get('analytic_distribution'):
                try:
                    distribution = eval(row['analytic_distribution']) if isinstance(
                        row['analytic_distribution'], str) else row['analytic_distribution']
                    result = []
                    for account_id, percentage in distribution.items():
                        account_name = account_dict.get(
                            str(account_id), f"Cuenta {account_id}")
                        result.append(f"{account_name}: {percentage}%")
                    row['analytic_distribution_display'] = ", ".join(result)
                except:
                    row['analytic_distribution_display'] = row['analytic_distribution']

            if row['unit_cost'] != 0 or (row['detailed_type'] == 'service' and services_included):
                continue

            else:
                query = """
                        SELECT
                            pol.price_unit AS unit_cost
                        FROM
                            purchase_order_line pol
                            JOIN purchase_order po ON pol.order_id = po.id
                        WHERE
                            pol.product_id = %s
                        ORDER BY
                            po.date_order DESC
                        LIMIT 1;
                """
                self.env.cr.execute(query, ((row['product_id']),))
                result = self.env.cr.fetchone()
                if result and result[0] and result[0] > 0.0:
                    row['unit_cost'] = result[0]
                    row['total_cost'] = row['unit_cost'] * \
                        row['quantity_invoiced'] if not row['refund_name'] else row['unit_cost'] * \
                        row['quantity_invoiced'] * -1
                    row['margin'] = abs(
                        row['sale_price_total']) - abs(row['total_cost'])
                    row['percentage'] = (abs(row['sale_price_total']) - abs(
                        row['total_cost'])) / abs(row['sale_price_total']) if row['sale_price_total'] else 0
                else:
                    product = self.env['product.product'].browse(
                        row['product_id'])
                    row['unit_cost'] = product.standard_price
                    row['total_cost'] = row['unit_cost'] * \
                        row['quantity_invoiced'] if not row['refund_name'] else row['unit_cost'] * \
                        row['quantity_invoiced'] * -1
                    row['margin'] = abs(
                        row['sale_price_total']) - abs(row['total_cost'])
                    row['percentage'] = (abs(row['sale_price_total']) - abs(
                        row['total_cost'])) / abs(row['sale_price_total']) if row['sale_price_total'] else 0

            if row['refund_name'] and (row['unit_cost'] > 0 or row['total_cost'] > 0):
                row['unit_cost'] = row['unit_cost'] * -1
                row['total_cost'] = row['total_cost'] * -1

            if not row['picking'] and not row['invoice_name']:
                row['refund_for_high_value'] = _("Refund for High Value")
                row['quantity_invoiced'] = 0.0
                row['weight'] = 0.0
                row['total_weight'] = 0.0

        return data

    @api.model
    def generate_report(self, start_date, end_date, services_included, partner_id=None, category_id=None, product_id=None):
        self.search([]).unlink()

        self.get_report_data(start_date, end_date, services_included,
                             partner_id, category_id, product_id)

        return {
            'name': _('Profitability by Product'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,pivot',
            'res_model': 'profitability.report',
            'target': 'current',
            'domain': [],
            'context': {},
        }
