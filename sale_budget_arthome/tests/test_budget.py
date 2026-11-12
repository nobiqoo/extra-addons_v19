from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged, new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestCommercialBudget(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('sales_team.group_sale_manager')
        cls.seller = new_test_user(cls.env, login='budget_seller', groups='sales_team.group_sale_salesman')
        cls.other_seller = new_test_user(cls.env, login='budget_other', groups='sales_team.group_sale_salesman')
        cls.budget = cls.env['sale.budget.monthly'].create({
            'user_id': cls.seller.id, 'date_start': '2026-05-01',
            'allocation_mode': 'category', 'amount_total_budget': 700000000, 'cartera_budget': 1000,
            'line_ids': [Command.create({'category_id': cls.product_a.categ_id.id, 'percent_allocation': 100})],
        })
        cls.budget.action_generate_weeks()

    def invoice(self, amount, date_value='2026-05-10', move_type='out_invoice', post=True, due_date=None):
        invoice = self.env['account.move'].create({
            'move_type': move_type, 'partner_id': self.partner_a.id,
            'invoice_user_id': self.seller.id, 'invoice_date': date_value,
            'invoice_date_due': due_date or date_value, 'date': date_value,
            'invoice_line_ids': [Command.create({
                'product_id': self.product_a.id, 'quantity': 1, 'price_unit': amount,
                'tax_ids': [Command.clear()],
            })],
        })
        if post:
            invoice.action_post()
            if due_date:
                # The collection target follows the due date displayed on the
                # invoice, as users do when reviewing the customer document.
                invoice.invoice_date_due = due_date
                invoice.line_ids.filtered(
                    lambda line: line.account_id.account_type == 'asset_receivable'
                ).date_maturity = due_date
        return invoice

    def test_calendar_and_confirmed_guards(self):
        self.assertEqual(len(self.budget.week_ids), 5)
        self.assertEqual(self.budget.week_ids[0].date_start, date(2026, 5, 1))
        self.assertEqual(self.budget.week_ids[-1].date_end, date(2026, 5, 31))
        self.assertAlmostEqual(sum(self.budget.week_ids.mapped('percent_allocation')), 100)
        self.budget.action_confirm()
        with self.assertRaises(UserError):
            self.budget.line_ids.write({'percent_allocation': 90})
        with self.assertRaises(UserError):
            self.budget.write({'amount_total_budget': 1})
        self.budget.action_draft()
        self.budget.week_ids[0].date_end = '2026-05-02'
        with self.assertRaises(ValidationError):
            self.budget.action_confirm()

    def test_distribution_validation_and_global(self):
        self.budget.line_ids.percent_allocation = 99
        with self.assertRaises(ValidationError):
            self.budget.action_confirm()
        self.budget.line_ids.unlink()
        self.budget.allocation_mode = 'global'
        self.budget.action_confirm()
        self.assertEqual(self.budget.state, 'confirmed')

    def test_six_calendar_weeks(self):
        self.budget.week_ids.unlink()
        self.budget.date_start = '2026-08-01'
        self.budget.action_generate_weeks()
        self.assertEqual(len(self.budget.week_ids), 6)
        self.budget.action_confirm()
        data = self.env['sale.budget.monthly'].get_dashboard('2026-08-01', self.budget.id)
        self.assertAlmostEqual(sum(d['budget'] for d in data['days']), 700000000, places=2)

    def test_confirm_generates_missing_weeks(self):
        budget = self.env['sale.budget.monthly'].create({
            'user_id': self.seller.id,
            'date_start': '2026-07-01',
            'allocation_mode': 'global',
            'amount_total_budget': 1000,
        })
        self.assertFalse(budget.week_ids)
        budget.action_confirm()
        self.assertEqual(budget.state, 'confirmed')
        self.assertEqual(len(budget.week_ids), 5)
        self.assertAlmostEqual(sum(budget.week_ids.mapped('percent_allocation')), 100)
        self.assertEqual(budget.week_ids[0].date_start, date(2026, 7, 1))
        self.assertEqual(budget.week_ids[-1].date_end, date(2026, 7, 31))

    def test_live_invoices_credit_notes_dashboard_and_pivot(self):
        self.budget.action_confirm()
        self.invoice(1000)
        self.invoice(100, move_type='out_refund')
        self.invoice(500, post=False)
        self.invoice(500, date_value='2026-06-01')
        self.budget.invalidate_recordset()
        self.assertEqual(self.budget.amount_real_sales, 900)
        self.assertEqual(self.budget.line_ids.real_amount, 900)
        report = self.env['sale.budget.report'].search([('budget_id', '=', self.budget.id)])
        self.assertEqual(report.amount_real_sales, 900)
        data = self.env['sale.budget.monthly'].with_user(self.seller).get_dashboard('2026-05-01', self.budget.id)
        self.assertEqual(data['real'], 900)
        self.assertEqual(data['days'][-1]['cumulative_real'], 900)
        day = next(row for row in data['days'] if row['date'] == '2026-05-10')
        self.assertEqual(day['real'], 900)
        self.assertAlmostEqual(day['daily_compliance'], 100 * day['real'] / day['budget'])
        self.assertEqual(sum(row['real'] for row in data['categories']), 900)
        self.assertEqual(len(data['sales']), 2)
        self.assertEqual(sum(row['amount'] for row in data['sales']), 900)
        self.assertEqual({row['type'] for row in data['sales']}, {'Factura', 'Nota crédito'})
        self.assertAlmostEqual(sum(day['budget'] for day in data['days']), 700000000, places=2)

    def test_overdue_partial_collection_and_snapshot(self):
        invoice = self.invoice(1000, date_value='2026-04-10')
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': '2026-05-12', 'amount': 400})._create_payments()
        self.budget.action_confirm()
        self.assertEqual(self.budget.portfolio_total, 1000)
        self.assertEqual(self.budget.portfolio_overdue, 1000)
        self.assertEqual(self.budget.cartera_real_collected, 400)
        self.assertEqual(self.budget.cartera_pending, 600)
        collection = self.env['sale.budget.monthly'].get_dashboard('2026-05-01', self.budget.id)['collection_invoices']
        row = next(item for item in collection if item['document'] == invoice.name)
        self.assertEqual(row['total'], 1000)
        self.assertEqual(row['paid'], 400)
        self.assertEqual(row['pending'], 600)
        self.assertEqual(row['status'], 'Pago parcial')
        self.assertTrue(row['overdue'])
        self.budget.invalidate_recordset()
        self.assertEqual(self.budget.cartera_paid_invoice_count, 0)
        self.assertEqual(self.budget.cartera_pending_invoice_count, 1)
        self.assertEqual(self.budget.cartera_pending_invoice_amount, 600)
        data = self.env['sale.budget.monthly'].get_dashboard('2026-05-01', self.budget.id)
        self.assertEqual(sum(day['collection'] for day in data['days']), 400)
        self.assertEqual(next(day['collection'] for day in data['days'] if day['date'] == '2026-05-12'), 400)
        self.assertEqual(len(data['collection_payments']), 1)
        self.assertEqual(data['collection_payments'][0]['invoice'], invoice.name)
        self.assertEqual(data['collection_payments'][0]['amount'], 400)
        self.env.flush_all()
        self.assertEqual(self.env['sale.budget.report'].browse(self.budget.id).cartera_real_collected, 400)
        # A credit note reconciled against the same invoice is not cash collection.
        refund = self.invoice(100, date_value='2026-05-13', move_type='out_refund')
        (invoice.line_ids + refund.line_ids).filtered(lambda l: l.account_id.account_type == 'asset_receivable').reconcile()
        self.budget.invalidate_recordset()
        self.assertEqual(self.budget.cartera_real_collected, 400)
        invoice.line_ids.remove_move_reconcile()
        self.budget.invalidate_recordset()
        self.assertEqual(self.budget.cartera_real_collected, 0)

    def test_same_month_invoice_payment_is_excluded_from_collection(self):
        invoice = self.invoice(1000)
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': '2026-05-10', 'amount': 400})._create_payments()
        self.assertEqual(self.budget.cartera_real_collected, 0)
        self.budget.action_confirm()
        data = self.env['sale.budget.monthly'].get_dashboard('2026-05-01', self.budget.id)
        self.assertEqual(data['collected'], 0)
        self.assertFalse(data['collection_payments'])
        self.assertFalse(data['collection_invoices'])
        self.env.flush_all()
        self.assertEqual(self.env['sale.budget.report'].browse(self.budget.id).cartera_real_collected, 0)

    def test_manual_bank_entry_reconciled_with_invoice_is_collection(self):
        invoice = self.invoice(1000, date_value='2026-04-10', due_date='2026-04-30')
        receivable_line = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable'
        )
        bank_journal = self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'bank'),
            ('default_account_id', '!=', False),
        ], limit=1)
        bank_entry = self.env['account.move'].create({
            'date': '2026-05-12',
            'journal_id': bank_journal.id,
            'line_ids': [
                Command.create({
                    'name': 'Ingreso bancario',
                    'account_id': bank_journal.default_account_id.id,
                    'debit': 1000,
                }),
                Command.create({
                    'name': 'Pago de factura',
                    'account_id': receivable_line.account_id.id,
                    'partner_id': invoice.commercial_partner_id.id,
                    'credit': 1000,
                }),
            ],
        })
        bank_entry.action_post()
        (receivable_line + bank_entry.line_ids.filtered(
            lambda line: line.account_id == receivable_line.account_id
        )).reconcile()

        self.budget.invalidate_recordset()
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertEqual(self.budget.cartera_real_collected, 1000)
        self.assertEqual(self.budget.cartera_paid_invoice_count, 1)
        self.assertEqual(self.budget.cartera_paid_invoice_amount, 1000)
        self.assertEqual(self.budget.cartera_pending_invoice_count, 0)
        self.assertEqual(self.budget.cartera_pending_invoice_amount, 0)
        self.budget.action_confirm()
        data = self.env['sale.budget.monthly'].get_dashboard('2026-05-01', self.budget.id)
        self.assertEqual(data['collected'], 1000)
        self.assertEqual(data['collection_payments'][0]['payment'], bank_entry.name)

    def test_automatic_collection_target_and_manual_adjustment(self):
        overdue_invoice = self.invoice(1000, date_value='2026-09-01', due_date='2026-09-10')
        self.invoice(2000, date_value='2026-09-15', due_date='2026-10-15')
        budget = self.env['sale.budget.monthly'].create({
            'user_id': self.seller.id,
            'date_start': '2026-10-01',
            'allocation_mode': 'global',
            'amount_total_budget': 5000,
        })
        self.assertFalse(budget.cartera_budget_manual)
        self.assertEqual(budget.cartera_overdue_calculated, 1000)
        self.assertEqual(budget.cartera_due_month_calculated, 2000)
        self.assertEqual(budget.cartera_budget_calculated, 3000)
        self.assertEqual(budget.cartera_budget, 3000)

        self.invoice(500, date_value='2026-09-20', due_date='2026-10-20')
        self.assertEqual(budget.cartera_budget, 3500)

        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=overdue_invoice.ids,
        ).create({'payment_date': '2026-09-22', 'amount': 400})._create_payments()
        self.assertEqual(budget.cartera_overdue_calculated, 600)
        self.assertEqual(budget.cartera_budget, 3100)

        budget.cartera_budget = 9999
        self.assertTrue(budget.cartera_budget_manual)
        self.invoice(250, date_value='2026-09-21', due_date='2026-10-25')
        self.assertEqual(budget.cartera_budget_calculated, 3350)
        self.assertEqual(budget.cartera_budget, 9999)
        budget.action_use_calculated_collection_target()
        self.assertFalse(budget.cartera_budget_manual)
        self.assertEqual(budget.cartera_budget, 3350)
        overdue_invoice.line_ids.remove_move_reconcile()
        self.assertEqual(budget.cartera_budget, 3750)

    def test_form_zero_target_remains_automatic_and_paid_invoice_is_removed(self):
        self.invoice(1000, date_value='2026-09-01', due_date='2026-09-10')
        due_invoice = self.invoice(2000, date_value='2026-09-15', due_date='2026-10-15')
        budget = self.env['sale.budget.monthly'].create({
            'user_id': self.seller.id,
            'date_start': '2026-10-01',
            'allocation_mode': 'global',
            'amount_total_budget': 5000,
            # This is what an untouched monetary input sends from the form.
            'cartera_budget': 0,
            'cartera_budget_manual': False,
        })
        self.assertFalse(budget.cartera_budget_manual)
        self.assertEqual(budget.cartera_budget, 3000)
        action = budget.action_view_collection_target_invoices()
        self.assertEqual(
            set(self.env['account.move'].search(action['domain']).ids),
            set(budget._collection_target_lines().move_id.ids),
        )

        new_invoice = self.invoice(500, date_value='2026-09-20', due_date='2026-10-20')
        self.assertEqual(budget.cartera_budget, 3500)

        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=new_invoice.ids,
        ).create({'payment_date': '2026-09-25', 'amount': 500})._create_payments()
        self.assertEqual(new_invoice.payment_state, 'paid')
        self.assertEqual(budget.cartera_budget, 3000)
        self.assertNotIn(new_invoice, budget._collection_target_lines().move_id)

        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=due_invoice.ids,
        ).create({'payment_date': '2026-09-26', 'amount': 2000})._create_payments()
        self.assertEqual(due_invoice.payment_state, 'paid')
        self.assertEqual(budget.cartera_due_month_calculated, 0)
        self.assertEqual(budget.cartera_budget, 1000)

    def test_payment_during_budget_month_does_not_reduce_collection_target(self):
        # A sale invoiced and paid in October is current-month business, not
        # collection of the portfolio that existed when October began.
        current_month_invoice = self.invoice(10500, date_value='2026-10-04', due_date='2026-10-13')
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=current_month_invoice.ids,
        ).create({'payment_date': '2026-10-04', 'amount': 10500})._create_payments()

        # This invoice existed before October and is due during October, so it
        # belongs to the collection target and its October payments are recaudo.
        invoice = self.invoice(1764, date_value='2026-09-29', due_date='2026-10-14')
        budget = self.env['sale.budget.monthly'].create({
            'user_id': self.seller.id,
            'date_start': '2026-10-01',
            'allocation_mode': 'global',
            'amount_total_budget': 5000,
        })
        self.assertEqual(budget.cartera_budget, 1764)
        self.assertEqual(budget.cartera_due_month_calculated, 1764)
        self.assertEqual(budget.cartera_collected_target_calculated, 0)
        self.assertEqual(budget.cartera_real_collected, 0)

        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': '2026-10-05', 'amount': 1050})._create_payments()

        budget.invalidate_recordset([
            'cartera_budget_calculated', 'cartera_overdue_calculated',
            'cartera_due_month_calculated', 'cartera_collected_target_calculated',
            'cartera_real_collected', 'cartera_compliance',
        ])
        target_lines = budget._collection_target_lines()
        entries = budget._collection_entries()
        self.assertEqual(
            (
                invoice.payment_state,
                invoice.amount_residual,
                sum(target_lines.mapped('amount_residual')),
                [entry['amount'] for entry in entries],
                budget.cartera_collected_target_calculated,
                budget.cartera_budget_calculated,
                budget.cartera_budget,
                budget.cartera_real_collected,
            ),
            ('partial', 714, 714, [1050], 1050, 1764, 1764, 1050),
        )
        self.assertAlmostEqual(budget.cartera_compliance, 100 * 1050 / 1764)
        action = budget.action_view_collection_target_invoices()
        self.assertIn(invoice, self.env['account.move'].search(action['domain']))
        self.assertNotIn(current_month_invoice, self.env['account.move'].search(action['domain']))

    def test_access_isolated_between_advisers(self):
        team = self.env['crm.team'].create({
            'name': 'Equipo sin acceso por liderazgo',
            'user_id': self.other_seller.id,
        })
        self.budget.team_id = team
        self.budget.action_confirm()
        model = self.env['sale.budget.monthly'].with_user(self.other_seller)
        self.assertFalse(model.search([('id', '=', self.budget.id)]))
        self.assertEqual(model.get_dashboard('2026-05-01', self.budget.id)['count'], 0)
        with self.assertRaises(AccessError):
            self.budget.with_user(self.other_seller).read(['amount_real_sales'])
        with self.assertRaises(AccessError):
            self.budget.with_user(self.seller).write({'notes': 'Forbidden'})
        self.assertFalse(self.env['sale.budget.report'].with_user(self.other_seller).search([('id', '=', self.budget.id)]))
        self.assertTrue(self.env['sale.budget.monthly'].search([('id', '=', self.budget.id)]))

    def test_category_week_override(self):
        weeks = self.budget.week_ids.sorted('date_start')
        self.env['sale.budget.schedule'].create({
            'line_id': self.budget.line_ids.id, 'week_id': weeks[0].id, 'percent_allocation': 100,
        })
        self.budget.action_confirm()
        data = self.env['sale.budget.monthly'].get_dashboard('2026-05-01', self.budget.id)
        self.assertAlmostEqual(sum(d['budget'] for d in data['days'][:3]), 700000000, places=2)
        self.assertAlmostEqual(sum(d['budget'] for d in data['days'][3:]), 0, places=2)
        with self.assertRaises(UserError):
            self.budget.line_ids.schedule_ids.percent_allocation = 50

    def test_category_pivot_includes_sales_without_target(self):
        self.budget.action_confirm()
        self.invoice(1000)
        extra = self.invoice(300, post=False)
        category = self.env['product.category'].create({'name': 'Sin meta'})
        product = self.product_a.copy({'name': 'Extra', 'categ_id': category.id})
        extra.invoice_line_ids.product_id = product
        extra.action_post()
        self.env.flush_all()
        report = self.env['sale.budget.category.report'].search([('budget_id', '=', self.budget.id)])
        self.assertEqual(sum(report.mapped('real_amount')), 1300)
        self.assertEqual(sum(report.mapped('budget_amount')), 700000000)
        self.assertEqual(report.filtered(lambda r: not r.category_id).real_amount, 300)

    def test_multicompany_dashboard_and_reports(self):
        other_company = self.env['res.company'].sudo().create({'name': 'Otra compañía de prueba'})
        self.seller.sudo().company_ids += other_company
        other_budget = self.env['sale.budget.monthly'].sudo().with_company(other_company).create({
            'user_id': self.seller.id, 'company_id': other_company.id, 'date_start': '2026-05-01',
            'allocation_mode': 'global', 'amount_total_budget': 1000,
        })
        other_budget.action_generate_weeks()
        other_budget.action_confirm()
        self.budget.action_confirm()
        self.env.flush_all()
        context = {'allowed_company_ids': [self.env.company.id]}
        restricted = self.env['sale.budget.monthly'].with_user(self.seller).with_context(**context)
        self.assertEqual(restricted.get_dashboard('2026-05-01')['budget'], 700000000)
        for model in ['sale.budget.report', 'sale.budget.category.report']:
            self.assertFalse(self.env[model].with_user(self.seller).with_context(**context).search([
                ('company_id', '=', other_company.id)]))

    def test_rounding_preserves_monthly_total(self):
        self.budget.amount_total_budget = 1
        self.budget.line_ids.percent_allocation = 33.333333
        category = self.env['product.category'].create({'name': 'Segunda categoría'})
        self.env['sale.budget.line'].create({
            'budget_id': self.budget.id, 'category_id': category.id, 'percent_allocation': 66.666667,
        })
        self.budget.action_confirm()
        data = self.env['sale.budget.monthly'].get_dashboard('2026-05-01', self.budget.id)
        self.assertAlmostEqual(sum(row['budget'] for row in data['days']), 1)
        self.assertAlmostEqual(sum(row['budget'] for row in data['categories']), 1)
        for line in self.budget.line_ids:
            filtered = self.env['sale.budget.monthly'].get_dashboard('2026-05-01', self.budget.id, category_id=line.category_id.id)
            self.assertEqual(filtered['budget'], line.budget_amount)
            self.assertAlmostEqual(sum(row['budget'] for row in filtered['days']), line.budget_amount)

    def test_estimate_units_with_reference_price(self):
        self.budget.line_ids.write({'uom_id': self.uom_unit.id, 'reference_unit_price': 100000})
        self.assertEqual(self.budget.line_ids.estimated_quantity, 7000)
