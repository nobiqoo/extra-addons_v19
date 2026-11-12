import calendar
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare


class SaleBudgetMonthly(models.Model):
    _name = 'sale.budget.monthly'
    _description = 'Presupuesto comercial mensual'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, user_id'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    user_id = fields.Many2one('res.users', string='Asesor', required=True,
                              domain=[('share', '=', False)], tracking=True)
    team_id = fields.Many2one('crm.team', string='Equipo', check_company=True, tracking=True)
    zone = fields.Char(string='Zona / sucursal', tracking=True)
    city = fields.Char(string='Ciudad')
    state_id = fields.Many2one('res.country.state', string='Departamento')
    date_start = fields.Date(string='Mes', required=True,
                             default=lambda s: fields.Date.context_today(s).replace(day=1), tracking=True)
    date_end = fields.Date(string='Fin del mes', compute='_compute_date_end', store=True)
    state = fields.Selection([('draft', 'Borrador'), ('confirmed', 'Confirmado')],
                             string='Estado', default='draft', required=True, tracking=True)
    allocation_mode = fields.Selection([('category', 'Por categoría'), ('global', 'Global / sin categoría')],
                                       default='category', required=True, string='Distribución')
    amount_total_budget = fields.Monetary(string='Presupuesto de ventas', tracking=True)
    cartera_budget = fields.Monetary(string='Meta a recaudar', tracking=True)
    cartera_budget_calculated = fields.Monetary(
        compute='_compute_collection_target', string='Meta calculada',
        help='Saldo vencido pendiente más las cuotas que vencerán dentro del mes presupuestado.',
    )
    cartera_overdue_calculated = fields.Monetary(
        compute='_compute_collection_target', string='Facturas vencidas no pagadas',
    )
    cartera_due_month_calculated = fields.Monetary(
        compute='_compute_collection_target', string='Facturas por vencer en el mes',
    )
    cartera_collected_target_calculated = fields.Monetary(
        compute='_compute_collection_target', string='Pagado de la meta durante el mes',
        help='Pagos del mes aplicados a facturas emitidas antes del mes presupuestado.',
    )
    cartera_budget_manual = fields.Boolean(
        string='Meta ajustada manualmente', default=False, copy=False, readonly=True,
    )
    line_ids = fields.One2many('sale.budget.line', 'budget_id', string='Categorías', copy=True)
    week_ids = fields.One2many('sale.budget.week', 'budget_id', string='Planificación', copy=True)
    amount_real_sales = fields.Monetary(compute='_compute_metrics', string='Venta real')
    compliance_percentage = fields.Float(compute='_compute_metrics', string='Cumplimiento ventas (%)')
    cartera_real_collected = fields.Monetary(compute='_compute_metrics', string='Recaudo real')
    cartera_compliance = fields.Float(compute='_compute_metrics', string='Cumplimiento recaudo (%)')
    cartera_pending = fields.Monetary(compute='_compute_metrics', string='Pendiente de meta')
    cartera_paid_invoice_count = fields.Integer(
        compute='_compute_collection_invoice_summary', string='Cantidad de facturas pagadas',
    )
    cartera_paid_invoice_amount = fields.Monetary(
        compute='_compute_collection_invoice_summary', string='Valor de facturas pagadas',
    )
    cartera_pending_invoice_count = fields.Integer(
        compute='_compute_collection_invoice_summary', string='Cantidad de facturas pendientes',
    )
    cartera_pending_invoice_amount = fields.Monetary(
        compute='_compute_collection_invoice_summary', string='Saldo de facturas pendientes',
    )
    portfolio_total = fields.Monetary(string='Cartera al inicio', readonly=True, copy=False)
    portfolio_overdue = fields.Monetary(string='Vencida al inicio', readonly=True, copy=False)
    portfolio_due_month = fields.Monetary(string='Por vencer en el mes', readonly=True, copy=False)
    snapshot_date = fields.Date(string='Fecha de corte de cartera', readonly=True, copy=False)
    notes = fields.Text(string='Observaciones')

    _unique_month = models.Constraint('UNIQUE(company_id, user_id, date_start)',
                                      'Ya existe un presupuesto para este asesor, compañía y mes.')

    @api.depends('user_id.name', 'date_start')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s / %s' % (rec.user_id.name or '', rec.date_start or '')

    @api.depends('date_start')
    def _compute_date_end(self):
        for rec in self:
            rec.date_end = rec.date_start and rec.date_start.replace(
                day=calendar.monthrange(rec.date_start.year, rec.date_start.month)[1])

    @api.onchange('user_id')
    def _onchange_user(self):
        self.team_id = self.user_id.sale_team_id

    @api.onchange('user_id', 'date_start', 'company_id')
    def _onchange_collection_target(self):
        for rec in self.filtered(lambda budget: not budget.cartera_budget_manual):
            rec.cartera_budget = rec.cartera_budget_calculated

    @api.depends('user_id', 'date_start', 'date_end', 'company_id')
    def _compute_collection_target(self):
        calculation_date = fields.Date.context_today(self)
        for rec in self:
            overdue = due_month = collected_target = 0
            if rec.user_id and rec.company_id and rec.date_start and rec.date_end:
                lines = rec._collection_target_lines(calculation_date)
                overdue = sum(
                    line.amount_residual for line in lines
                    if line.move_id.invoice_date_due < calculation_date
                )
                due_month = sum(
                    line.amount_residual for line in lines
                    if calculation_date <= line.move_id.invoice_date_due
                    and rec.date_start <= line.move_id.invoice_date_due <= rec.date_end
                )
                collected_target = sum(
                    entry['amount'] for entry in rec._collection_entries()
                    if rec._is_collection_target_due_date(entry['due_date'], calculation_date)
                )
            rec.cartera_overdue_calculated = overdue
            rec.cartera_due_month_calculated = due_month
            rec.cartera_collected_target_calculated = collected_target
            rec.cartera_budget_calculated = overdue + due_month + collected_target

    def _is_collection_target_due_date(self, due_date, calculation_date=None):
        self.ensure_one()
        calculation_date = calculation_date or fields.Date.context_today(self)
        return bool(
            due_date
            and (
                due_date < calculation_date
                or max(calculation_date, self.date_start) <= due_date <= self.date_end
            )
        )

    def _collection_target_lines(self, calculation_date=None):
        """Open receivable installments included in the current collection target."""
        self.ensure_one()
        if not (self.user_id and self.company_id and self.date_start and self.date_end):
            return self.env['account.move.line']
        calculation_date = calculation_date or fields.Date.context_today(self)
        return self.env['account.move.line'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', '=', 'out_invoice'),
            ('move_id.invoice_user_id', '=', self.user_id.id),
            ('move_id.invoice_date', '<', self.date_start),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('move_id.invoice_date_due', '!=', False),
            ('amount_residual', '>', 0),
            '|',
            ('move_id.invoice_date_due', '<', calculation_date),
            '&', ('move_id.invoice_date_due', '>=', max(calculation_date, self.date_start)),
                 ('move_id.invoice_date_due', '<=', self.date_end),
        ])

    def _sync_auto_collection_target(self):
        automatic = self.filtered(lambda budget: not budget.cartera_budget_manual)
        for rec in automatic:
            rec.invalidate_recordset([
                'cartera_budget_calculated', 'cartera_overdue_calculated',
                'cartera_due_month_calculated', 'cartera_collected_target_calculated',
            ])
            rec.with_context(auto_collection_target=True).write({
                'cartera_budget': rec.cartera_budget_calculated,
            })
            # Leave the four informational values uncached so the form reads
            # the final residuals after Odoo completes the reconciliation.
            rec.invalidate_recordset([
                'cartera_budget_calculated', 'cartera_overdue_calculated',
                'cartera_due_month_calculated', 'cartera_collected_target_calculated',
            ])

    def action_use_calculated_collection_target(self):
        self._assert_draft()
        for rec in self:
            rec.invalidate_recordset([
                'cartera_budget_calculated', 'cartera_overdue_calculated',
                'cartera_due_month_calculated', 'cartera_collected_target_calculated',
            ])
            rec.with_context(auto_collection_target=True).write({
                'cartera_budget': rec.cartera_budget_calculated,
                'cartera_budget_manual': False,
            })
        return True

    def action_view_collection_target_invoices(self):
        self.ensure_one()
        self.check_access('read')
        calculation_date = fields.Date.context_today(self)
        paid_invoice_ids = [
            entry['invoice_id'] for entry in self._collection_entries()
            if self._is_collection_target_due_date(entry['due_date'], calculation_date)
        ]
        invoices = self._collection_target_lines(calculation_date).move_id | self.env['account.move'].browse(paid_invoice_ids)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Facturas incluidas en la meta de recaudo'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
            'context': {
                'default_move_type': 'out_invoice',
                'create': False,
            },
        }

    @api.constrains('date_start', 'amount_total_budget', 'cartera_budget', 'user_id', 'company_id')
    def _check_header(self):
        for rec in self:
            if rec.date_start.day != 1:
                raise ValidationError(_('El mes debe comenzar el día 1.'))
            if rec.amount_total_budget < 0 or rec.cartera_budget < 0:
                raise ValidationError(_('Los presupuestos no pueden ser negativos.'))
            if rec.company_id not in rec.user_id.company_ids:
                raise ValidationError(_('El asesor debe pertenecer a la compañía del presupuesto.'))

    def _assert_draft(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_('Regrese el presupuesto a borrador para modificar su planificación.'))

    def write(self, vals):
        protected = {'company_id', 'user_id', 'date_start', 'amount_total_budget', 'cartera_budget',
                     'allocation_mode', 'line_ids', 'week_ids', 'team_id', 'zone', 'city', 'state_id'}
        automatic_target = self.env.context.get('auto_collection_target')
        if protected.intersection(vals) and not automatic_target:
            self._assert_draft()
        if 'cartera_budget' in vals and not automatic_target:
            vals['cartera_budget_manual'] = True
        result = super().write(vals)
        if {'company_id', 'user_id', 'date_start'}.intersection(vals) and not automatic_target:
            self.filtered(lambda budget: not budget.cartera_budget_manual)._sync_auto_collection_target()
        if vals.get('state') == 'confirmed':
            self._validate_plan()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        automatic_target = self.env.context.get('auto_collection_target')
        submitted_targets = []
        for vals in vals_list:
            submitted_targets.append((
                'cartera_budget' in vals,
                vals.get('cartera_budget') or 0,
                vals.get('cartera_budget_manual') is True,
            ))
            if not automatic_target:
                # The web client sends the monetary field (usually zero, or the
                # onchange result) even when the user did not adjust it. Decide
                # whether it is manual only after the calculated value exists.
                vals['cartera_budget_manual'] = False
        records = super().create(vals_list)
        if not automatic_target:
            for rec, (target_provided, submitted_target, explicit_manual) in zip(records, submitted_targets):
                differs_from_calculation = target_provided and float_compare(
                    submitted_target,
                    rec.cartera_budget_calculated,
                    precision_rounding=rec.currency_id.rounding,
                )
                manual_target = explicit_manual or (
                    target_provided
                    and not rec.currency_id.is_zero(submitted_target)
                    and differs_from_calculation
                )
                if manual_target:
                    rec.with_context(auto_collection_target=True).write({
                        'cartera_budget_manual': True,
                    })
                else:
                    rec.with_context(auto_collection_target=True).write({
                        'cartera_budget': rec.cartera_budget_calculated,
                        'cartera_budget_manual': False,
                    })
        records.filtered(lambda r: r.state == 'confirmed')._validate_plan()
        return records

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        self._assert_draft()

    def _validate_plan(self):
        for rec in self:
            if rec.allocation_mode == 'category':
                if not rec.line_ids or float_compare(sum(rec.line_ids.mapped('percent_allocation')), 100, precision_digits=4):
                    raise ValidationError(_('La distribución por categorías debe sumar 100 %.'))
                categories = rec.line_ids.category_id
                for category in categories:
                    if category.parent_path and any(
                        int(parent) in (categories - category).ids
                        for parent in category.parent_path.strip('/').split('/')
                    ):
                        raise ValidationError(_('No mezcle categorías padre e hijas en el mismo presupuesto.'))
                for line in rec.line_ids:
                    if line.schedule_ids and float_compare(sum(line.schedule_ids.mapped('percent_allocation')), 100, precision_digits=4):
                        raise ValidationError(_('La distribución semanal propia de cada categoría debe sumar 100 %.'))
            elif rec.line_ids:
                raise ValidationError(_('Un presupuesto global no lleva líneas de metas por categoría.'))
            weeks = rec.week_ids.sorted('date_start')
            if not weeks or float_compare(sum(weeks.mapped('percent_allocation')), 100, precision_digits=4):
                raise ValidationError(_('Los tramos deben sumar 100 %.'))
            expected = rec.date_start
            for week in weeks:
                if week.date_start != expected:
                    raise ValidationError(_('Los tramos deben cubrir el mes sin huecos ni solapamientos.'))
                expected = week.date_end + timedelta(days=1)
            if expected != rec.date_end + timedelta(days=1):
                raise ValidationError(_('La planificación debe cubrir todo el mes.'))

    def action_confirm(self):
        for rec in self.filtered(lambda budget: not budget.week_ids):
            rec.action_generate_weeks()
        self._validate_plan()
        self._take_snapshot()
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_generate_weeks(self):
        """Real Monday–Sunday weeks clipped to month; 4, 5 or 6 ranges."""
        self._assert_draft()
        for rec in self:
            if rec.week_ids:
                raise UserError(_('Quite los tramos existentes antes de generar una nueva distribución.'))
            ranges = []
            start = rec.date_start
            while start <= rec.date_end:
                end = min(start + timedelta(days=6 - start.weekday()), rec.date_end)
                ranges.append((start, end))
                start = end + timedelta(days=1)
            percentage = round(100 / len(ranges), 6)
            rec.week_ids = [fields.Command.create({
                'name': self.env._('Semana %s', i + 1), 'date_start': start, 'date_end': end,
                'percent_allocation': percentage if i < len(ranges) - 1 else 100 - percentage * i,
            }) for i, (start, end) in enumerate(ranges)]

    def _invoice_lines(self):
        self.ensure_one()
        # Elevation is deliberately scoped to a budget already accessible to the caller.
        self.check_access('read')
        return self.env['account.move.line'].sudo().search([
            ('company_id', '=', self.company_id.id), ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('move_id.invoice_user_id', '=', self.user_id.id), ('display_type', '=', 'product'),
            ('move_id.invoice_date', '>=', self.date_start), ('move_id.invoice_date', '<=', self.date_end),
        ])

    def _collection_entries(self):
        """Cash/bank payments reconciled against customer invoices during the month."""
        self.ensure_one()
        self.check_access('read')
        partials = self.env['account.partial.reconcile'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('debit_move_id.move_id.invoice_user_id', '=', self.user_id.id),
            ('debit_move_id.move_id.move_type', '=', 'out_invoice'),
            ('debit_move_id.move_id.state', '=', 'posted'),
            ('debit_move_id.move_id.invoice_date', '<', self.date_start),
            ('credit_move_id.move_id.state', '=', 'posted'),
            ('credit_move_id.date', '>=', self.date_start), ('credit_move_id.date', '<=', self.date_end),
        ])
        return [{
            'id': p.id,
            'date': p.credit_move_id.date,
            'invoice': p.debit_move_id.move_id.name or '/',
            'invoice_id': p.debit_move_id.move_id.id,
            'partner': p.debit_move_id.move_id.partner_id.display_name,
            'payment': p.credit_move_id.move_id.name or '/',
            'amount': p.amount,
            'due_date': p.debit_move_id.move_id.invoice_date_due,
        } for p in partials if
            p.debit_move_id.account_id.account_type == 'asset_receivable'
            and (
                p.credit_move_id.move_id.origin_payment_id
                or p.credit_move_id.move_id.statement_line_id
                or p.credit_move_id.move_id.journal_id.type in ('bank', 'cash')
            )]

    def _collection_amount(self):
        return sum(entry['amount'] for entry in self._collection_entries())

    def _collection_invoice_rows(self):
        """Invoice payment position at the selected month's effective cut-off."""
        self.ensure_one()
        self.check_access('read')
        cutoff = min(fields.Date.context_today(self), self.date_end)
        opening_cutoff = self.date_start - timedelta(days=1)
        moves = self.env['account.move'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'posted'),
            ('move_type', '=', 'out_invoice'),
            ('invoice_user_id', '=', self.user_id.id),
            ('invoice_date', '<', self.date_start),
        ])

        def residual_at(line, date):
            amount = line.balance
            amount -= sum(p.amount for p in line.matched_credit_ids if p.max_date <= date)
            amount += sum(p.amount for p in line.matched_debit_ids if p.max_date <= date)
            return max(self.company_id.currency_id.round(amount), 0)

        rows = []
        for move in moves:
            receivable = move.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
            total = self.company_id.currency_id.round(sum(receivable.mapped('balance')))
            if total <= 0:
                continue
            opening = sum(residual_at(line, opening_cutoff) for line in receivable)
            if not opening:
                continue
            residuals = [(line, residual_at(line, cutoff)) for line in receivable]
            pending = self.company_id.currency_id.round(sum(amount for _line, amount in residuals))
            paid = max(self.company_id.currency_id.round(total - pending), 0)
            due_date = move.invoice_date_due or move.invoice_date
            overdue = bool(pending and due_date and due_date < cutoff)
            status = _('Pagada') if not pending else (_('Pago parcial') if paid else _('Pendiente'))
            rows.append({
                'id': move.id,
                'date': fields.Date.to_string(move.invoice_date),
                'document': move.name or '/',
                'partner': move.partner_id.display_name,
                'adviser': self.user_id.name,
                'due_date': fields.Date.to_string(due_date),
                'total': total,
                'paid': paid,
                'pending': pending,
                'status': status,
                'overdue': overdue,
            })
        return rows, cutoff

    @api.depends('user_id', 'date_start', 'date_end', 'company_id')
    def _compute_collection_invoice_summary(self):
        for rec in self:
            rows = rec._collection_invoice_rows()[0] if rec.id and rec.date_start else []
            paid_rows = [row for row in rows if not row['pending']]
            pending_rows = [row for row in rows if row['pending']]
            rec.cartera_paid_invoice_count = len(paid_rows)
            rec.cartera_paid_invoice_amount = sum(row['total'] for row in paid_rows)
            rec.cartera_pending_invoice_count = len(pending_rows)
            rec.cartera_pending_invoice_amount = sum(row['pending'] for row in pending_rows)

    @api.depends('amount_total_budget', 'cartera_budget', 'user_id', 'date_start', 'company_id')
    def _compute_metrics(self):
        for rec in self:
            sales = -sum(rec._invoice_lines().mapped('balance')) if rec.id and rec.date_start else 0
            collected = rec._collection_amount() if rec.id and rec.date_start else 0
            rec.amount_real_sales = sales
            rec.compliance_percentage = 100 * sales / rec.amount_total_budget if rec.amount_total_budget else 0
            rec.cartera_real_collected = collected
            rec.cartera_compliance = 100 * collected / rec.cartera_budget if rec.cartera_budget else 0
            rec.cartera_pending = max(rec.cartera_budget - collected, 0)

    def _take_snapshot(self):
        for rec in self:
            rec.check_access('write')
            lines = self.env['account.move.line'].sudo().search([
                ('company_id', '=', rec.company_id.id), ('move_id.state', '=', 'posted'),
                ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                ('move_id.invoice_user_id', '=', rec.user_id.id),
                ('account_id.account_type', '=', 'asset_receivable'), ('date', '<', rec.date_start),
            ])
            total = overdue = due = 0
            for line in lines:
                # Reconstruct residual at cut-off, including reconciliations made later.
                amount = line.balance - sum(p.amount for p in line.matched_credit_ids if p.max_date < rec.date_start)
                amount += sum(p.amount for p in line.matched_debit_ids if p.max_date < rec.date_start)
                maturity = line.move_id.invoice_date_due or line.date_maturity or line.date
                total += amount
                overdue += amount if maturity < rec.date_start else 0
                due += amount if rec.date_start <= maturity <= rec.date_end else 0
            rec.write({'portfolio_total': total, 'portfolio_overdue': overdue,
                       'portfolio_due_month': due, 'snapshot_date': rec.date_start - timedelta(days=1)})

    def action_dashboard(self):
        self.ensure_one()
        return {'type': 'ir.actions.client', 'tag': 'sale_budget_arthome.dashboard',
                'name': _('Cumplimiento comercial'), 'params': {'budget_id': self.id}}

    @api.model
    def get_dashboard(self, month=None, budget_id=None, team_id=None, zone=None, category_id=None):
        date = fields.Date.to_date(month) if month else fields.Date.context_today(self).replace(day=1)
        domain = [('date_start', '=', date.replace(day=1)), ('state', '=', 'confirmed')]
        if budget_id:
            domain.append(('id', '=', int(budget_id)))
        if team_id:
            domain.append(('team_id', '=', int(team_id)))
        if zone:
            domain.append(('zone', '=', zone))
        budgets = self.search(domain)
        currencies = budgets.currency_id
        if len(currencies) > 1:
            raise UserError(_('Seleccione una sola compañía o compañías con la misma moneda.'))
        currency = currencies or self.env.company.currency_id
        daily = defaultdict(lambda: {'budget': 0, 'real': 0, 'collection': 0})
        categories = defaultdict(lambda: {'budget': 0, 'real': 0})
        sales = []
        collection_invoices = {}
        collection_payments = {}
        collection_cutoff = date
        total = real = collected = collection_budget = 0
        selected_category = int(category_id) if category_id else None
        for budget in budgets:
            allocation = {line.category_id.id: line for line in budget.line_ids}
            total += (allocation[selected_category].budget_amount
                      if selected_category in allocation else 0) if selected_category else budget.amount_total_budget
            collection_budget += budget.cartera_budget
            collection_entries = budget._collection_entries()
            collected += sum(entry['amount'] for entry in collection_entries)
            for entry in collection_entries:
                date_key = fields.Date.to_string(entry['date'])
                daily[date_key]['collection'] += entry['amount']
                collection_payments[entry['id']] = dict(entry, date=date_key)
            invoice_rows, budget_cutoff = budget._collection_invoice_rows()
            collection_cutoff = max(collection_cutoff, budget_cutoff)
            collection_invoices.update({row['id']: row for row in invoice_rows})
            for line in budget.line_ids:
                if not selected_category or selected_category == line.category_id.id:
                    categories[line.category_id.display_name]['budget'] += line.budget_amount
            if not selected_category and budget.allocation_mode == 'global':
                categories[_('Global / sin categoría')]['budget'] += budget.amount_total_budget
            for week in budget.week_ids:
                days = (week.date_end - week.date_start).days + 1
                week_amount = (allocation[selected_category]._week_amount(week)
                               if selected_category in allocation else 0) if selected_category else week.budget_amount
                # Round to currency precision and put the residual on the last day.
                amount = currency.round(week_amount / days)
                for offset in range(days):
                    key = fields.Date.to_string(week.date_start + timedelta(days=offset))
                    daily[key]['budget'] += amount if offset < days - 1 else week_amount - amount * (days - 1)
            for line in budget._invoice_lines():
                category = line.product_id.categ_id
                parents = [int(p) for p in (category.parent_path or '').strip('/').split('/') if p]
                matching = next((allocation[c] for c in reversed(parents) if c in allocation), None)
                if selected_category and (not matching or matching.category_id.id != selected_category):
                    continue
                amount = -line.balance
                real += amount
                label = (matching.category_id.display_name if matching else _('Sin meta de categoría'))
                if budget.allocation_mode == 'global':
                    label = _('Global / sin categoría')
                categories[label]['real'] += amount
                daily[fields.Date.to_string(line.move_id.invoice_date)]['real'] += amount
                sales.append({
                    'id': line.id,
                    'date': fields.Date.to_string(line.move_id.invoice_date),
                    'document': line.move_id.name or '/',
                    'type': _('Nota crédito') if line.move_id.move_type == 'out_refund' else _('Factura'),
                    'partner': line.move_id.partner_id.display_name,
                    'adviser': budget.user_id.name,
                    'product': line.product_id.display_name,
                    'category': label,
                    'amount': amount,
                })
        rows = []
        cum_budget = cum_real = 0
        for day in range(1, calendar.monthrange(date.year, date.month)[1] + 1):
            key = fields.Date.to_string(date.replace(day=day))
            values = daily[key]
            cum_budget += values['budget']
            cum_real += values['real']
            rows.append(dict(date=key, **values, cumulative_budget=cum_budget,
                             cumulative_real=cum_real,
                             daily_compliance=100 * values['real'] / values['budget'] if values['budget'] else None,
                             compliance=100 * cum_real / cum_budget if cum_budget else None))
        choices = self.search([('date_start', '=', date.replace(day=1)), ('state', '=', 'confirmed')])
        return {
            'currency': currency.name, 'budget': total, 'real': real,
            'compliance': 100 * real / total if total else None,
            'collection_budget': collection_budget, 'collected': collected,
            'collection_compliance': 100 * collected / collection_budget if collection_budget else None,
            'pending': max(collection_budget - collected, 0), 'days': rows,
            'categories': [dict(name=k, **v, compliance=100 * v['real'] / v['budget'] if v['budget'] else None)
                           for k, v in sorted(categories.items())],
            'advisers': [{'id': b.id, 'name': b.user_id.name} for b in choices],
            'teams': [{'id': t.id, 'name': t.name} for t in choices.team_id],
            'zones': sorted(set(choices.mapped('zone')) - {False}),
            'category_options': [{'id': c.id, 'name': c.display_name} for c in choices.line_ids.category_id],
            'sales': sorted(sales, key=lambda row: (row['date'], row['document'], row['id']), reverse=True),
            'collection_invoices': sorted(
                collection_invoices.values(),
                key=lambda row: (row['due_date'], row['document'], row['id']), reverse=True,
            ),
            'collection_payments': sorted(
                collection_payments.values(),
                key=lambda row: (row['date'], row['payment'], row['id']), reverse=True,
            ),
            'collection_cutoff': fields.Date.to_string(collection_cutoff),
            'count': len(budgets),
        }


class BudgetPlanMixin(models.AbstractModel):
    _name = 'sale.budget.plan.mixin'
    _description = 'Controles de planificación comercial'
    _check_company_auto = True

    budget_id = fields.Many2one('sale.budget.monthly', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='budget_id.company_id', store=True)
    currency_id = fields.Many2one(related='budget_id.currency_id')
    percent_allocation = fields.Float(string='% de meta', digits=(16, 6), required=True)
    @api.constrains('percent_allocation')
    def _check_values(self):
        for rec in self:
            if not 0 <= rec.percent_allocation <= 100:
                raise ValidationError(_('El porcentaje debe estar entre 0 y 100.'))

    @api.model_create_multi
    def create(self, vals_list):
        self.env['sale.budget.monthly'].browse([v['budget_id'] for v in vals_list if v.get('budget_id')])._assert_draft()
        return super().create(vals_list)

    def write(self, vals):
        self.budget_id._assert_draft()
        if vals.get('budget_id'):
            self.env['sale.budget.monthly'].browse(vals['budget_id'])._assert_draft()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        self.budget_id._assert_draft()


class SaleBudgetLine(models.Model):
    _name = 'sale.budget.line'
    _description = 'Distribución de presupuesto por categoría'
    _inherit = 'sale.budget.plan.mixin'

    category_id = fields.Many2one('product.category', string='Categoría', required=True)
    budget_amount = fields.Monetary(compute='_compute_amount', store=True, string='Presupuesto')
    quantity_target = fields.Float(string='Meta en unidades', help='Meta independiente del valor monetario.')
    reference_unit_price = fields.Monetary(string='Precio unitario de referencia',
                                          help='Opcional. Permite estimar unidades a partir del presupuesto de la categoría.')
    estimated_quantity = fields.Float(string='Unidades estimadas', compute='_compute_estimated_quantity')
    uom_id = fields.Many2one('uom.uom', string='Unidad de la meta')
    schedule_ids = fields.One2many('sale.budget.schedule', 'line_id', string='Distribución semanal propia', copy=True)
    real_amount = fields.Monetary(compute='_compute_real', string='Venta real')
    compliance_rate = fields.Float(compute='_compute_real', string='Cumplimiento (%)')

    _unique_category = models.Constraint('UNIQUE(budget_id, category_id)', 'La categoría ya está asignada.')

    @api.depends('budget_amount', 'reference_unit_price')
    def _compute_estimated_quantity(self):
        for rec in self:
            rec.estimated_quantity = rec.budget_amount / rec.reference_unit_price if rec.reference_unit_price else 0

    @api.constrains('quantity_target', 'uom_id', 'reference_unit_price')
    def _check_quantity(self):
        for rec in self:
            if rec.quantity_target < 0 or rec.reference_unit_price < 0 or ((rec.quantity_target or rec.reference_unit_price) and not rec.uom_id):
                raise ValidationError(_('La meta de unidades debe ser no negativa y tener unidad de medida.'))

    @api.depends('percent_allocation', 'budget_id.amount_total_budget', 'budget_id.line_ids.percent_allocation')
    def _compute_amount(self):
        for line in self:
            siblings = line.budget_id.line_ids
            total = line.budget_id.amount_total_budget
            if siblings and line == siblings[-1] and not float_compare(sum(siblings.mapped('percent_allocation')), 100, precision_digits=4):
                line.budget_amount = total - sum(line.currency_id.round(total * other.percent_allocation / 100) for other in siblings[:-1])
            else:
                line.budget_amount = line.currency_id.round(total * line.percent_allocation / 100)

    def _week_amount(self, week):
        self.ensure_one()
        schedule = self.schedule_ids.filtered(lambda s: s.week_id == week)
        percent = sum(schedule.mapped('percent_allocation')) if self.schedule_ids else week.percent_allocation
        # Residual on the last range keeps the monthly budget exact in currency precision.
        weeks = self.budget_id.week_ids.sorted('date_start')
        if weeks and week == weeks[-1]:
            return self.budget_amount - sum(self.currency_id.round(self.budget_amount * (
                sum(self.schedule_ids.filtered(lambda s: s.week_id == w).mapped('percent_allocation'))
                if self.schedule_ids else w.percent_allocation) / 100) for w in weeks[:-1])
        return self.currency_id.round(self.budget_amount * percent / 100)

    @api.depends('budget_id', 'category_id', 'budget_amount')
    def _compute_real(self):
        for budget in self.budget_id:
            lines = budget._invoice_lines()
            for rec in self.filtered(lambda r: r.budget_id == budget):
                rec.real_amount = -sum(line.balance for line in lines if
                    str(rec.category_id.id) in (line.product_id.categ_id.parent_path or '').strip('/').split('/'))
                rec.compliance_rate = 100 * rec.real_amount / rec.budget_amount if rec.budget_amount else 0


class SaleBudgetWeek(models.Model):
    _name = 'sale.budget.week'
    _description = 'Tramo semanal del presupuesto'
    _inherit = 'sale.budget.plan.mixin'
    _order = 'date_start, id'

    name = fields.Char(string='Tramo', required=True)
    date_start = fields.Date(string='Desde', required=True)
    date_end = fields.Date(string='Hasta', required=True)
    budget_amount = fields.Monetary(compute='_compute_amount', string='Presupuesto')
    real_amount = fields.Monetary(compute='_compute_real', string='Venta real')
    compliance_rate = fields.Float(compute='_compute_real', string='Cumplimiento (%)')

    @api.depends('percent_allocation', 'budget_id.amount_total_budget', 'budget_id.line_ids.budget_amount',
                 'budget_id.line_ids.schedule_ids.percent_allocation', 'budget_id.week_ids.percent_allocation',
                 'budget_id.line_ids.schedule_ids.week_id', 'budget_id.allocation_mode', 'date_start')
    def _compute_amount(self):
        for rec in self:
            if rec.budget_id.allocation_mode == 'category':
                rec.budget_amount = sum(line._week_amount(rec) for line in rec.budget_id.line_ids)
            else:
                weeks = rec.budget_id.week_ids.sorted('date_start')
                total = rec.budget_id.amount_total_budget
                if weeks and rec == weeks[-1]:
                    rec.budget_amount = total - sum(rec.currency_id.round(total * w.percent_allocation / 100) for w in weeks[:-1])
                else:
                    rec.budget_amount = rec.currency_id.round(total * rec.percent_allocation / 100)

    @api.constrains('date_start', 'date_end', 'budget_id')
    def _check_dates(self):
        for rec in self:
            if not rec.budget_id.date_start <= rec.date_start <= rec.date_end <= rec.budget_id.date_end:
                raise ValidationError(_('El tramo debe estar dentro del mes y tener fechas válidas.'))

    @api.depends('date_start', 'date_end', 'budget_id', 'budget_amount')
    def _compute_real(self):
        for budget in self.budget_id:
            lines = budget._invoice_lines()
            for rec in self.filtered(lambda r: r.budget_id == budget):
                rec.real_amount = -sum(line.balance for line in lines if rec.date_start <= line.move_id.invoice_date <= rec.date_end)
                rec.compliance_rate = 100 * rec.real_amount / rec.budget_amount if rec.budget_amount else 0


class SaleBudgetSchedule(models.Model):
    _name = 'sale.budget.schedule'
    _description = 'Meta semanal específica de una categoría'
    _inherit = 'sale.budget.plan.mixin'

    line_id = fields.Many2one('sale.budget.line', required=True, ondelete='cascade')
    budget_id = fields.Many2one(related='line_id.budget_id', store=True, precompute=True)
    week_id = fields.Many2one('sale.budget.week', string='Tramo', required=True, ondelete='cascade')
    budget_amount = fields.Monetary(compute='_compute_amount', string='Presupuesto de categoría en el tramo')

    _unique_schedule = models.Constraint('UNIQUE(line_id, week_id)', 'El tramo ya está asignado a esta categoría.')

    @api.depends('percent_allocation', 'line_id.budget_amount', 'week_id')
    def _compute_amount(self):
        for rec in self:
            rec.budget_amount = rec.line_id._week_amount(rec.week_id) if rec.week_id else 0

    @api.constrains('line_id', 'week_id')
    def _check_parent(self):
        for rec in self:
            if rec.line_id.budget_id != rec.week_id.budget_id:
                raise ValidationError(_('La categoría y el tramo deben pertenecer al mismo presupuesto.'))

    @api.model_create_multi
    def create(self, vals_list):
        self.env['sale.budget.line'].browse([v['line_id'] for v in vals_list]).budget_id._assert_draft()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('line_id'):
            self.env['sale.budget.line'].browse(vals['line_id']).budget_id._assert_draft()
        return super().write(vals)


def _sync_collection_budgets(env, company_user_keys):
    """Refresh targets that have not been manually adjusted."""
    Budget = env['sale.budget.monthly'].sudo()
    for company_id, user_id in company_user_keys:
        if company_id and user_id:
            budgets = Budget.search([
                ('company_id', '=', company_id),
                ('user_id', '=', user_id),
            ])
            budgets.invalidate_recordset([
                'cartera_budget_calculated', 'cartera_overdue_calculated',
                'cartera_due_month_calculated', 'cartera_collected_target_calculated',
            ])
            budgets.filtered(lambda budget: not budget.cartera_budget_manual)._sync_auto_collection_target()


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _collection_budget_keys(self):
        return {
            (move.company_id.id, move.invoice_user_id.id)
            for move in self
            if move.move_type == 'out_invoice' and move.company_id and move.invoice_user_id
        }

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        _sync_collection_budgets(self.env, moves._collection_budget_keys())
        return moves

    def write(self, vals):
        relevant = {
            'state', 'move_type', 'company_id', 'invoice_user_id', 'invoice_date_due',
            'invoice_payment_term_id', 'invoice_line_ids', 'line_ids',
        }
        keys = self._collection_budget_keys() if relevant.intersection(vals) else set()
        result = super().write(vals)
        if relevant.intersection(vals):
            _sync_collection_budgets(self.env, keys | self._collection_budget_keys())
        return result

    def unlink(self):
        keys = self._collection_budget_keys()
        result = super().unlink()
        _sync_collection_budgets(self.env, keys)
        return result


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def write(self, vals):
        relevant = {
            'date_maturity', 'account_id', 'balance', 'debit', 'credit', 'move_id',
            'amount_residual', 'amount_residual_currency',
        }
        moves = self.move_id if relevant.intersection(vals) else self.env['account.move']
        keys = moves._collection_budget_keys()
        result = super().write(vals)
        if relevant.intersection(vals):
            _sync_collection_budgets(self.env, keys | self.move_id._collection_budget_keys())
        return result


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    def _collection_budget_keys(self):
        return self.debit_move_id.move_id._collection_budget_keys()

    @api.model_create_multi
    def create(self, vals_list):
        partials = super().create(vals_list)
        _sync_collection_budgets(self.env, partials._collection_budget_keys())
        return partials

    def unlink(self):
        keys = self._collection_budget_keys()
        result = super().unlink()
        _sync_collection_budgets(self.env, keys)
        return result
