import base64
from datetime import date, datetime
from io import BytesIO

from PIL import Image

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestRepairOrderFormat(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_a = new_test_user(cls.env, login='metromat_a', groups='stock.group_stock_user', name='Usuario A')
        cls.user_b = new_test_user(cls.env, login='metromat_b', groups='stock.group_stock_user', name='Usuario B')
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente', 'email': 'cliente@test.co', 'phone': '123'})
        cls.contact = cls.env['res.partner'].create({
            'name': 'Contacto', 'parent_id': cls.customer.id,
            'function': 'Gestora', 'email': 'contacto@test.co', 'phone': '456',
        })
        cls.category = cls.env['product.category'].create({'name': 'Radiometros'})
        cls.product = cls.env['product.product'].create({'name': 'Equipo', 'categ_id': cls.category.id})
        buffer = BytesIO()
        Image.new('RGB', (2000, 1000), 'red').save(buffer, format='PNG')
        cls.png = base64.b64encode(buffer.getvalue())

    def _create_order(self, **vals):
        return self.env['repair.order'].create({
            'partner_id': self.customer.id,
            'product_id': self.product.id,
            **vals,
        })

    def _upload(self, user, mimetype='image/png', name='foto.png'):
        return self.env['ir.attachment'].with_user(user).create({
            'name': name,
            'datas': self.png,
            'mimetype': mimetype,
            'res_model': 'repair.order',
            'res_id': 0,
        })

    def _render(self, report_xmlid, order, user=None):
        report = self.env['ir.actions.report']
        if user:
            report = report.with_user(user)
        return report._render_qweb_html(report_xmlid, order.ids)[0].decode()

    def test_service_types_are_managed_by_stock_manager(self):
        ServiceType = self.env['repair.service.type']
        with self.assertRaises(AccessError):
            ServiceType.with_user(self.user_a).create({'name': 'Otro'})
        manager = new_test_user(self.env, login='metromat_m', groups='stock.group_stock_manager')
        service_type = ServiceType.with_user(manager).create({'name': 'Otro'})
        order = self._create_order()
        self.assertIn(service_type, order._get_format_service_types())

    def test_contact_falls_back_to_customer(self):
        order = self._create_order()
        self.assertEqual(order._get_format_contact_data()['email'], 'cliente@test.co')
        order.contact_id = self.contact
        self.assertEqual(order._get_format_contact_data(), {
            'name': 'Contacto', 'function': 'Gestora', 'email': 'contacto@test.co', 'phone': '456',
        })

    def test_dates_are_in_spanish_and_user_timezone(self):
        order = self._create_order().with_context(tz='America/Bogota')
        self.assertEqual(order._format_full_date(datetime(2026, 5, 21, 2, 0)), 'miércoles, 20 de mayo de 2026')
        self.assertEqual(order._format_long_date(date(2026, 6, 30)), '30 de junio de 2026')
        self.assertEqual(order._format_long_date(False), '')

    def test_equipment_data_uses_each_equipment(self):
        brand = self.env['product.brand'].create({'name': 'Spectroline'})
        equipments = self.env['product.maintenance'].create([
            {'name': 'Uno', 'product_id': self.product.id, 'brand_id': brand.id, 'model': 'XP-2000'},
            {'name': 'Dos', 'product_id': self.product.id},
        ])
        order = self._create_order()
        self.assertEqual(order._get_format_equipment_data(), [
            {'category': 'Radiometros', 'brand': '', 'model': '', 'serial': ''},
        ])
        order.maintenance_equipment_ids = [(6, 0, equipments.ids)]
        data = order._get_format_equipment_data()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0], {'category': 'Radiometros', 'brand': 'Spectroline', 'model': 'XP-2000', 'serial': ''})

    def test_customer_sign_date_follows_signature(self):
        order = self._create_order()
        self.assertFalse(order.customer_sign_date)
        order.sign_client = self.png
        self.assertTrue(order.customer_sign_date)
        order.customer_sign_date = '2026-06-30'
        order.sign_client = self.png
        self.assertEqual(str(order.customer_sign_date), '2026-06-30')
        order.sign_client = False
        self.assertFalse(order.customer_sign_date)

    def test_inventory_item_is_position(self):
        order = self._create_order(inventory_line_ids=[
            (0, 0, {'description': 'Cargador', 'sequence': 2}),
            (0, 0, {'description': 'Equipo', 'sequence': 1}),
        ])
        order.invalidate_recordset(['inventory_line_ids'])
        self.assertEqual(
            [(line.item, line.description) for line in order.inventory_line_ids],
            [(1, 'Equipo'), (2, 'Cargador')],
        )

    def test_image_is_readable_by_other_user(self):
        image = self._upload(self.user_a)
        order = self._create_order()
        order.with_user(self.user_a).reception_image_ids = [(6, 0, image.ids)]
        self.assertEqual((image.res_model, image.res_id), ('repair.order', order.id))
        html = self._render('stock_metromat.report_repair_order_reception', order, self.user_b)
        self.assertIn('data:image/png;base64', html)

    def test_foreign_attachment_is_not_rebound(self):
        partner_attachment = self.env['ir.attachment'].create({
            'name': 'foto.png', 'datas': self.png, 'mimetype': 'image/png',
            'res_model': 'res.partner', 'res_id': self.customer.id,
        })
        order = self._create_order(delivery_image_ids=[(6, 0, partner_attachment.ids)])
        self.assertTrue(order.delivery_image_ids)
        self.assertEqual(partner_attachment.res_model, 'res.partner')

    def test_only_jpg_and_png_are_accepted(self):
        attachment = self.env['ir.attachment'].create({
            'name': 'nota.txt', 'raw': b'texto', 'mimetype': 'text/plain',
        })
        with self.assertRaises(ValidationError):
            self._create_order(reception_image_ids=[(6, 0, attachment.ids)])

    def test_reception_report_content(self):
        service_type = self.env.ref('stock_metromat.service_type_calibration')
        order = self._create_order(
            contact_id=self.contact.id,
            service_type_ids=[(6, 0, service_type.ids)],
            under_warranty=True,
            reception_date='2026-05-20 15:00:00',
            received_by_id=self.user_a.id,
            inventory_line_ids=[(0, 0, {
                'description': 'Cargador', 'reception_comment': 'Comentario entrada', 'delivery_comment': 'Comentario salida',
            })],
        )
        html = self._render('stock_metromat.report_repair_order_reception', order)
        self.assertIn('FORMATO DE INGRESO DE EQUIPOS', html)
        self.assertIn('contacto@test.co', html)
        self.assertIn('miércoles, 20 de mayo de 2026', html)
        self.assertIn('Comentario entrada', html)
        self.assertNotIn('Comentario salida', html)

    def test_delivery_report_content(self):
        order = self._create_order(
            delivery_issue_date='2026-06-30',
            delivered_by_id=self.user_b.id,
            customer_signer_name='Firmante',
            customer_signer_vat='1020',
            sign_client=self.png,
            inventory_line_ids=[(0, 0, {
                'description': 'Cargador', 'reception_comment': 'Comentario entrada', 'delivery_comment': 'Comentario salida',
            })],
        )
        html = self._render('stock_metromat.report_repair_order_delivery', order, self.user_a)
        self.assertIn('FORMATO DE REMISIÓN DE EQUIPOS', html)
        self.assertIn('30 de junio de 2026', html)
        self.assertIn('Usuario B', html)
        self.assertIn('Firmante', html)
        self.assertIn('1020', html)
        self.assertIn('Comentario salida', html)
        self.assertNotIn('Comentario entrada', html)
