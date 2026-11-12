from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestCustomerActivity(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('sales_team.group_sale_manager')

    def _order(self, partner):
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [Command.create({
                'product_id': self.product_a.id,
                'product_uom_qty': 1,
                'price_unit': 100,
            })],
        })

    def _set_order_date(self, order, date_value):
        order.date_order = datetime.combine(date_value, time(12))

    def test_customer_activity_lifecycle_and_configurable_period(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'sale_budget_arthome.customer_inactivity_months', 6,
        )
        today = fields.Date.context_today(self.env['res.partner'])
        partner = self.env['res.partner'].create({'name': 'Cliente actividad'})
        never_bought = self.env['res.partner'].create({'name': 'Cliente sin historial'})
        self.assertEqual(never_bought.x_customer_activity_status, 'inactive')
        self.assertFalse(never_bought.x_last_sale_date)

        old_order = self._order(partner)
        old_order.action_confirm()
        old_date = today - relativedelta(months=7)
        self._set_order_date(old_order, old_date)
        self.assertEqual(partner.x_last_sale_date, old_date)
        self.assertEqual(partner.x_customer_activity_status, 'inactive')

        recent_order = self._order(partner)
        recent_order.action_confirm()
        recent_date = today - relativedelta(months=2)
        self._set_order_date(recent_order, recent_date)
        self.assertEqual(partner.x_last_sale_date, recent_date)
        self.assertEqual(partner.x_customer_activity_status, 'active')
        self.assertEqual(recent_order.x_last_sale_date, recent_date)
        self.assertEqual(recent_order.x_customer_activity_status, 'active')

        recent_order.action_cancel()
        self.assertEqual(partner.x_last_sale_date, old_date)
        self.assertEqual(partner.x_customer_activity_status, 'inactive')

        self.env['ir.config_parameter'].sudo().set_param(
            'sale_budget_arthome.customer_inactivity_months', 12,
        )
        self.env['res.partner']._cron_update_customer_activity()
        self.assertEqual(partner.x_customer_activity_status, 'active')

        recovered_order = self._order(partner)
        recovered_order.action_confirm()
        self.assertEqual(partner.x_last_sale_date, today)
        self.assertEqual(partner.x_customer_activity_status, 'active')
        self.assertEqual(
            self.env['res.partner'].search_count([
                ('id', '=', partner.id),
                ('x_customer_activity_status', '=', 'active'),
                ('x_last_sale_date', '=', today),
            ]),
            1,
        )

    def test_activity_fields_are_stored_and_exportable(self):
        for model_name in ('res.partner', 'sale.order'):
            model = self.env[model_name]
            self.assertTrue(model._fields['x_last_sale_date'].store)
            self.assertTrue(model._fields['x_customer_activity_status'].store)
        exported = self.env['res.partner'].export_data([
            'name', 'email', 'x_last_sale_date', 'x_customer_activity_status',
        ])
        self.assertIn('datas', exported)
