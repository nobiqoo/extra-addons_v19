from odoo import fields, models, tools


class SaleBudgetReport(models.Model):
    _name = 'sale.budget.report'
    _description = 'Cumplimiento comercial por asesor y mes'
    _auto = False
    _rec_name = 'user_id'

    budget_id = fields.Many2one('sale.budget.monthly', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    user_id = fields.Many2one('res.users', string='Asesor', readonly=True)
    team_id = fields.Many2one('crm.team', string='Equipo', readonly=True)
    zone = fields.Char(string='Zona', readonly=True)
    city = fields.Char(string='Ciudad', readonly=True)
    state_id = fields.Many2one('res.country.state', string='Departamento', readonly=True)
    date_start = fields.Date(string='Mes', readonly=True)
    amount_total_budget = fields.Monetary(string='Presupuesto ventas', readonly=True)
    amount_real_sales = fields.Monetary(string='Venta real', readonly=True)
    cartera_budget = fields.Monetary(string='Meta a recaudar', readonly=True)
    cartera_real_collected = fields.Monetary(string='Recaudo real', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE VIEW sale_budget_report AS
            SELECT b.id, b.id AS budget_id, b.company_id, b.currency_id, b.user_id,
                   b.team_id, b.zone, b.city, b.state_id, b.date_start,
                   b.amount_total_budget, b.cartera_budget,
                   COALESCE(s.amount, 0) AS amount_real_sales,
                   COALESCE(c.amount, 0) AS cartera_real_collected
            FROM sale_budget_monthly b
            LEFT JOIN LATERAL (
                SELECT SUM(-l.balance) AS amount
                FROM account_move_line l JOIN account_move m ON m.id = l.move_id
                WHERE m.company_id = b.company_id AND m.invoice_user_id = b.user_id
                  AND m.state = 'posted' AND m.move_type IN ('out_invoice', 'out_refund')
                  AND m.invoice_date BETWEEN b.date_start AND b.date_end
                  AND l.display_type = 'product'
            ) s ON TRUE
            LEFT JOIN LATERAL (
                SELECT SUM(p.amount) AS amount
                FROM account_partial_reconcile p
                JOIN account_move_line debit ON debit.id = p.debit_move_id
                JOIN account_move invoice ON invoice.id = debit.move_id
                JOIN account_account a ON a.id = debit.account_id
                JOIN account_move_line credit ON credit.id = p.credit_move_id
                JOIN account_move payment ON payment.id = credit.move_id
                WHERE p.company_id = b.company_id AND invoice.invoice_user_id = b.user_id
                  AND invoice.move_type = 'out_invoice' AND invoice.state = 'posted'
                  AND invoice.invoice_date < b.date_start
                  AND payment.state = 'posted' AND a.account_type = 'asset_receivable'
                  AND (payment.origin_payment_id IS NOT NULL OR payment.statement_line_id IS NOT NULL)
                  AND credit.date BETWEEN b.date_start AND b.date_end
            ) c ON TRUE
            WHERE b.state = 'confirmed'
        ''')


class SaleBudgetCategoryReport(models.Model):
    _name = 'sale.budget.category.report'
    _description = 'Cumplimiento por categoría de negocio'
    _auto = False

    budget_id = fields.Many2one('sale.budget.monthly', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    user_id = fields.Many2one('res.users', string='Asesor', readonly=True)
    team_id = fields.Many2one('crm.team', string='Equipo', readonly=True)
    zone = fields.Char(string='Zona', readonly=True)
    date_start = fields.Date(string='Mes', readonly=True)
    category_id = fields.Many2one('product.category', string='Categoría', readonly=True)
    allocation_mode = fields.Selection([('category', 'Por categoría'), ('global', 'Global / sin categoría')], readonly=True)
    budget_amount = fields.Monetary(string='Presupuesto', readonly=True)
    real_amount = fields.Monetary(string='Venta real', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE VIEW sale_budget_category_report AS
            WITH sales AS (
                SELECT m.company_id, m.invoice_user_id, m.invoice_date, pc.parent_path, -l.balance AS amount
                FROM account_move_line l
                JOIN account_move m ON m.id = l.move_id
                LEFT JOIN product_product p ON p.id = l.product_id
                LEFT JOIN product_template pt ON pt.id = p.product_tmpl_id
                LEFT JOIN product_category pc ON pc.id = pt.categ_id
                WHERE m.state = 'posted' AND m.move_type IN ('out_invoice', 'out_refund')
                  AND l.display_type = 'product'
            )
            SELECT line.id AS id, b.id AS budget_id, b.company_id, b.currency_id, b.user_id,
                   b.team_id, b.zone, b.date_start, line.category_id, b.allocation_mode,
                   line.budget_amount, COALESCE(SUM(s.amount), 0) AS real_amount
            FROM sale_budget_line line
            JOIN sale_budget_monthly b ON b.id = line.budget_id
            JOIN product_category category ON category.id = line.category_id
            LEFT JOIN sales s ON s.company_id = b.company_id AND s.invoice_user_id = b.user_id
                AND s.invoice_date BETWEEN b.date_start AND b.date_end
                AND s.parent_path LIKE category.parent_path || '%'
            WHERE b.state = 'confirmed' AND b.allocation_mode = 'category'
            GROUP BY line.id, b.id
            UNION ALL
            SELECT -b.id AS id, b.id AS budget_id, b.company_id, b.currency_id, b.user_id,
                   b.team_id, b.zone, b.date_start, NULL AS category_id, b.allocation_mode,
                   CASE WHEN b.allocation_mode = 'global' THEN b.amount_total_budget ELSE 0 END AS budget_amount,
                   COALESCE(SUM(s.amount), 0) AS real_amount
            FROM sale_budget_monthly b
            LEFT JOIN sales s ON s.company_id = b.company_id AND s.invoice_user_id = b.user_id
                AND s.invoice_date BETWEEN b.date_start AND b.date_end
                AND (b.allocation_mode = 'global' OR NOT EXISTS (
                    SELECT 1 FROM sale_budget_line line JOIN product_category category ON category.id = line.category_id
                    WHERE line.budget_id = b.id AND s.parent_path LIKE category.parent_path || '%'
                ))
            WHERE b.state = 'confirmed'
            GROUP BY b.id
            HAVING b.allocation_mode = 'global' OR COUNT(s.amount) > 0
        ''')
