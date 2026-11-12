# -*- coding: utf-8 -*-

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

SUMMARY = "Confirmar la orden de compra"
SUMMARY_BUDGET = "Confirmar la orden de compra por falta de presupuesto"


@tagged('post_install', '-at_install')
class TestApprovalActivities(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.pr_approval_po = True
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('purchase.group_purchase_manager').id]
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.buyer, cls.user_a, cls.user_b, cls.user_c = (
            Users.create({
                'name': login, 'login': login, 'email': f'{login}@example.com',
                'group_ids': [Command.set(groups)],
            })
            for login in ('pa_buyer', 'pa_a', 'pa_b', 'pa_c')
        )
        cls.partner = cls.env['res.partner'].create({'name': 'Proveedor'})
        cls.product = cls.env['product.product'].create({'name': 'Producto', 'standard_price': 100.0})

    def _matrix(self, lines, **vals):
        return self.env['purchase.approval.setting'].create({
            'name': 'Matriz',
            'company_id': self.env.company.id,
            'approval_line_ids': [
                Command.create({'user_ids': [Command.set(users.ids)], 'approval_type': 'without_condition'})
                for users in lines
            ],
            **vals,
        })

    def _order(self, matrix):
        order = self.env['purchase.order'].with_user(self.buyer).create({
            'partner_id': self.partner.id,
            'approval_config_id': matrix.id,
            'order_line': [Command.create({'product_id': self.product.id, 'product_qty': 1, 'price_unit': 100.0})],
        })
        order.button_request_approval()
        return order

    def _open(self, order, summary=SUMMARY):
        activities = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'purchase.order'), ('res_id', '=', order.id), ('summary', '=', summary),
        ])
        return activities.user_id

    def test_line_with_several_users(self):
        """Basta uno de los usuarios de la línea: se cierra también la del compañero."""
        order = self._order(self._matrix([self.user_a | self.user_b], approval_minimum=1))
        self.assertEqual(self._open(order), self.user_a | self.user_b)
        order.with_user(self.user_a).action_approve()
        self.assertEqual(order.state, 'approved')
        self.assertFalse(self._open(order))

    def test_minimum_reached_closes_pending_lines(self):
        """Con el mínimo cumplido, las líneas que siguen pendientes ya no deben actuar."""
        order = self._order(self._matrix([self.user_a, self.user_b], approval_minimum=1))
        order.with_user(self.user_a).action_approve()
        self.assertEqual(order.state, 'approved')
        self.assertFalse(self._open(order))

    def test_partial_approval_keeps_pending_users(self):
        order = self._order(self._matrix([self.user_a, self.user_b, self.user_c], approval_minimum=2))
        order.with_user(self.user_a).action_approve()
        self.assertEqual(order.state, 'in approval')
        self.assertEqual(self._open(order), self.user_b | self.user_c)
        order.with_user(self.user_b).action_approve()
        self.assertEqual(order.state, 'approved')
        self.assertFalse(self._open(order))

    def test_user_in_two_lines(self):
        order = self._order(self._matrix(
            [self.user_a | self.user_b, self.user_a | self.user_c], approval_minimum=2))
        order.with_user(self.user_b).action_approve()
        self.assertEqual(order.state, 'in approval')
        self.assertEqual(self._open(order), self.user_a | self.user_c)
        order.with_user(self.user_c).action_approve()
        self.assertEqual(order.state, 'approved')
        self.assertFalse(self._open(order))

    def test_approval_in_sequence(self):
        order = self._order(self._matrix(
            [self.user_a, self.user_b], approval_minimum=2, approval_with_sequence=True))
        self.assertEqual(self._open(order), self.user_a)
        order.with_user(self.user_a).action_approve()
        self.assertEqual(self._open(order), self.user_b)
        order.with_user(self.user_b).action_approve()
        self.assertEqual(order.state, 'approved')
        self.assertFalse(self._open(order))

    def test_outsider_does_not_close(self):
        order = self._order(self._matrix([self.user_a | self.user_b], approval_minimum=1))
        order.with_user(self.user_c).action_approve()
        self.assertEqual(order.state, 'in approval')
        self.assertEqual(self._open(order), self.user_a | self.user_b)

    def test_refuse_then_draft_then_request_again(self):
        order = self._order(self._matrix([self.user_a | self.user_b, self.user_c], approval_minimum=2))
        order.with_user(self.user_a).action_refuse()
        self.assertEqual(order.state, 'refused')
        self.assertFalse(self._open(order))
        order.with_user(self.buyer).action_request_draft()
        self.assertFalse(self._open(order))
        order.with_user(self.buyer).button_request_approval()
        self.assertEqual(self._open(order), self.user_a | self.user_b | self.user_c)
        count = self.env['mail.activity'].sudo().search_count([
            ('res_model', '=', 'purchase.order'), ('res_id', '=', order.id), ('summary', '=', SUMMARY),
        ])
        self.assertEqual(count, 3)

    def test_cancel(self):
        order = self._order(self._matrix([self.user_a | self.user_b], approval_minimum=1))
        order.with_user(self.buyer).button_cancel()
        self.assertEqual(order.state, 'cancel')
        self.assertFalse(self._open(order))

    def test_budget_approval_closes_all(self):
        matrix = self._matrix([self.user_c], approval_minimum=1)
        matrix.user_approvals_by_budget = self.user_a | self.user_b
        order = self.env['purchase.order'].with_user(self.buyer).create({
            'partner_id': self.partner.id,
            'approval_config_id': matrix.id,
            'order_line': [Command.create({'product_id': self.product.id, 'product_qty': 1, 'price_unit': 100.0})],
        })
        order.button_request_approval_without_budget()
        self.assertEqual(self._open(order, SUMMARY_BUDGET), self.user_a | self.user_b)
        wizard = self.env['purchase.appoval.reason.budget.wizard'].with_user(self.user_a).create({
            'order_id': order.id, 'reason_approval_by_budget': 'Prueba',
        })
        wizard.approva_budget()
        self.assertEqual(order.state, 'approved')
        self.assertFalse(self._open(order, SUMMARY_BUDGET))

    def test_budget_refuse_closes_all(self):
        matrix = self._matrix([self.user_c], approval_minimum=1)
        matrix.user_approvals_by_budget = self.user_a | self.user_b
        order = self.env['purchase.order'].with_user(self.buyer).create({
            'partner_id': self.partner.id,
            'approval_config_id': matrix.id,
            'order_line': [Command.create({'product_id': self.product.id, 'product_qty': 1, 'price_unit': 100.0})],
        })
        order.button_request_approval_without_budget()
        order.with_user(self.user_b).action_refuse_budget()
        self.assertEqual(order.state, 'refused')
        self.assertFalse(self._open(order, SUMMARY_BUDGET))
