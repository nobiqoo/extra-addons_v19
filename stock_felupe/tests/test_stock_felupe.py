from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockFelupe(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Felupe Test'})
        cls.product = cls.env['product.product'].create({
            'name': 'Producto Felupe Test',
            'is_storable': True,
            'standard_price': 100.0,
            'list_price': 150.0,
            'margin_percentage': 0.60,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
        })
        cls.line = cls.env['sale.order.line'].create({
            'order_id': cls.order.id,
            'product_id': cls.product.id,
            'product_uom_id': cls.product.uom_id.id,
            'product_uom_qty': 1.0,
            'price_unit': 150.0,
            'purchase_price': 100.0,
        })

    def test_margin_is_computed_over_cost_and_restricted(self):
        self.assertAlmostEqual(self.line.margin, 50.0)
        self.assertAlmostEqual(self.line.margin_percent, 0.50)

        with self.assertRaises(ValidationError):
            self.line._check_minimum_margin()

        self.order.sale_margin = True
        self.line._check_minimum_margin()

    def test_zero_quantity_has_a_complete_margin_compute(self):
        self.line.product_uom_qty = 0.0
        self.assertEqual(self.line.margin_percent, 0.0)
        self.assertEqual(self.line.margin, 0.0)

    def test_negative_product_margin_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.product.product_tmpl_id.margin_percentage = -0.01

    def test_margin_warning_creates_activity(self):
        responsible = self.env.ref('base.user_admin')
        wizard = self.env['margin.warning.wizard'].create({
            'line_id': self.order.id,
            'message': 'Revisar margen de prueba',
            'res_users_sale_activity': [(6, 0, responsible.ids)],
        })
        wizard.action_continue()

        activity = self.env['mail.activity'].sudo().search([
            ('res_model_id', '=', self.env['ir.model']._get_id('sale.order')),
            ('res_id', '=', self.order.id),
            ('user_id', '=', responsible.id),
        ])
        self.assertTrue(activity)
        self.assertEqual(activity.note, '<p>Revisar margen de prueba</p>')

    def test_picking_preparation_states(self):
        picking = self.env['stock.picking'].new({'state': 'confirmed'})
        picking._compute_picking_preparation_state()
        self.assertEqual(picking.picking_preparation_state, 'in_preparation')

        picking.state = 'done'
        picking._compute_picking_preparation_state()
        self.assertEqual(picking.picking_preparation_state, 'prepared')

    def test_byproduct_cost_sharing(self):
        finished_product = self.env['product.product'].create({
            'name': 'Producto Terminado Felupe Test',
            'is_storable': True,
        })
        component = self.env['product.product'].create({
            'name': 'Componente Felupe Test',
            'is_storable': True,
            'standard_price': 20.0,
        })
        byproduct = self.env['product.product'].create({
            'name': 'Subproducto Felupe Test',
            'is_storable': True,
        })
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': finished_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'product_uom_id': finished_product.uom_id.id,
            'bom_line_ids': [Command.create({
                'product_id': component.id,
                'product_qty': 10.0,
                'product_uom_id': component.uom_id.id,
            })],
            'byproduct_ids': [Command.create({
                'product_id': byproduct.id,
                'product_qty': 2.0,
                'product_uom_id': byproduct.uom_id.id,
                'cost_share': 25.0,
            })],
        })
        production = self.env['mrp.production'].create({
            'product_id': finished_product.id,
            'product_qty': 1.0,
            'product_uom_id': finished_product.uom_id.id,
            'bom_id': bom.id,
        })
        production.action_confirm()
        byproduct_move = production.move_byproduct_ids

        byproduct_move._compute_cost_sharing()

        self.assertAlmostEqual(byproduct_move.cost_sharing_float, 25.0)
