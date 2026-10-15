from odoo import api, fields, models, _
from odoo.exceptions import UserError
from logging import getLogger

_logger = getLogger(__name__)


class ProfitabilityReport(models.Model):
    _name = 'profitability.report'
    _description = 'Profitability by Product Report'

    move_line_id = fields.Many2one('account.move.line', 'Apunte')
    date = fields.Date('Fecha')
    order_name = fields.Char('Orden de Venta')
    invoice_name = fields.Char('Factura')
    refund_name = fields.Char('Nota Crédito')
    refund_for_high_value = fields.Char('Reembolso por Valor diferente')
    analytic_distribution = fields.Char('Distibusción Analítica')
    analytic_distribution_display = fields.Char('Cuenta Analítica')
    user_id = fields.Many2one('res.users', 'Vendedor')
    partner_id = fields.Many2one('res.partner', 'Cliente')
    product_id = fields.Many2one('product.product', 'Producto')
    category_id = fields.Many2one('product.category', 'Categoría')
    picking = fields.Char('Remisión')
    detailed_type = fields.Selection([
        ('consu', 'Consumible'),
        ('service', 'Servicio'),
        ('combo', 'Combo'),
        ('product', 'Producto'),])  # 'product' legacy (<=17); en 18/19 es consu/service/combo
    quantity_invoiced = fields.Float('Cantidad Facturada')
    weight = fields.Float('Peso')
    total_weight = fields.Float('Peso Total')
    unit_cost = fields.Float('Costo')
    total_cost = fields.Float('Costo Total')
    sale_price = fields.Float('Precio de Venta')
    sale_price_total = fields.Float('Total Precio de Venta')
    margin = fields.Float('Margen')
    percentage = fields.Float('Porcentage')

    @api.model
    def get_report_data(self, start_date, end_date, services_included, partner_id=None, category_id=None, product_id=None):
        additional_conditions = ""
        params = [start_date, end_date, self.env.company.id]

        # Odoo 19: el modelo uom.category fue eliminado. Las UoM ahora forman un
        # árbol (relative_uom_id / parent_path). Una unidad es de "Peso" si su
        # raíz es la unidad de referencia de peso (gramo). Se detecta por
        # parent_path ('<gram_id>/...'). Si no se encuentra, el fallback usa el
        # peso del producto.
        weight_ref = self.env.ref(
            'uom.product_uom_gram', raise_if_not_found=False)
        weight_root_id = weight_ref.id if weight_ref else 0

        if partner_id:
            additional_conditions += " AND rp.id = %s"
            params.append(partner_id)
        if category_id:
            additional_conditions += " AND pc.id = %s"
            params.append(category_id)
        if product_id:
            additional_conditions += " AND pp.id = %s"
            params.append(product_id)

        query = f"""
            SELECT DISTINCT ON (aml.id)
                aml.id AS move_line_id,
                COALESCE(sp.date_done, sp.scheduled_date, am.date) AS date,
                am.invoice_origin AS order_name,
                CASE WHEN am.move_type = 'out_invoice' THEN am.name END AS invoice_name,
                CASE WHEN am.move_type = 'out_refund' THEN am.name ELSE NULL END AS refund_name,
                aml.analytic_distribution AS analytic_distribution,
                am.invoice_user_id AS user_id,
                rp.id AS partner_id,
                pp.id AS product_id,
                pc.id AS category_id,
                sp.name AS picking,
                pt.type AS detailed_type,
                CASE WHEN am.move_type = 'out_refund' THEN ABS(aml.quantity) * (-1) ELSE aml.quantity END AS quantity_invoiced,
                pp.weight AS weight,
                CASE WHEN uom.parent_path LIKE '{weight_root_id}/%%' THEN aml.quantity ELSE aml.quantity * pp.weight END AS total_weight,
                CASE WHEN am.move_type = 'out_refund' THEN ABS(COALESCE(mv_cost.unit_cost, 0)) * (-1) ELSE COALESCE(mv_cost.unit_cost, 0) END AS unit_cost,
                CASE WHEN am.move_type = 'out_refund' THEN COALESCE(mv_cost.unit_cost, 0) * aml.quantity * (-1) ELSE COALESCE(mv_cost.unit_cost, 0) * aml.quantity END AS total_cost,
                CASE WHEN am.move_type = 'out_refund' THEN ABS(aml.price_unit * am.current_exchange_rate) * (-1) ELSE aml.price_unit * am.current_exchange_rate END AS sale_price,
                CASE WHEN am.move_type = 'out_refund' THEN ABS(aml.price_subtotal* am.current_exchange_rate) * (-1) ELSE aml.price_subtotal * am.current_exchange_rate END AS sale_price_total,
                ABS(aml.price_subtotal* am.current_exchange_rate) - (ABS(COALESCE(mv_cost.unit_cost, 0)) * aml.quantity) AS margin,
                (ABS(aml.price_subtotal*am.current_exchange_rate) - (ABS(COALESCE(mv_cost.unit_cost, 0)) * aml.quantity)) / NULLIF(ABS(aml.price_subtotal*am.current_exchange_rate), 0) AS percentage
            FROM account_move am
            JOIN account_move_line aml ON aml.move_id = am.id
            JOIN res_partner rp ON am.partner_id = rp.id
            JOIN product_product pp ON aml.product_id = pp.id
            JOIN product_template pt ON pp.product_tmpl_id = pt.id
            LEFT JOIN product_category pc ON pt.categ_id = pc.id
            LEFT JOIN uom_uom uom ON uom.id = aml.product_uom_id
            LEFT JOIN stock_picking sp ON sp.id = aml.stock_picking_id
            LEFT JOIN (
                -- Odoo 19: stock.valuation.layer fue eliminado; la valoración
                -- vive ahora directamente en stock_move (value / quantity).
                SELECT sm.picking_id, sm.product_id,
                    CASE WHEN SUM(sm.quantity) <> 0 THEN SUM(sm.value) / NULLIF(SUM(sm.quantity), 0) ELSE 0 END AS unit_cost
                FROM stock_move sm
                WHERE sm.state = 'done'
                GROUP BY sm.picking_id, sm.product_id
            ) mv_cost ON mv_cost.picking_id = sp.id AND mv_cost.product_id = pp.id
            WHERE am.move_type IN ('out_invoice', 'out_refund')
                AND am.state = 'posted'
                AND aml.product_id IS NOT NULL
                AND aml.display_type = 'product'
                AND am.date >= %s
                AND am.date <= %s
                AND am.company_id = %s
                {additional_conditions}
        """

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

            if row['refund_name'] and (row['unit_cost'] > 0 or row['total_cost'] > 0):
                row['unit_cost'] = row['unit_cost'] * -1
                row['total_cost'] = row['total_cost'] * -1

            if not row['picking'] and row['detailed_type'] != 'service':
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
            'name': _('Rentabilidad por Producto'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,pivot',
            'res_model': 'profitability.report',
            'target': 'current',
            'domain': [],
            'context': {},
        }
