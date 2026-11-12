# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestArchivarBidireccional(SafraCommon):
    """9-nov: archivar el producto archiva su línea en Referencias y al revés."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tela_b = cls.env['safra.fabric'].create({'code': 'ZT-B', 'name': 'Tela B Prueba'})
        cls.solo = cls._color(cls.tela, 'ZTSOLO', 'Solo Prueba')
        cls.doble = cls._color(cls.tela, 'ZTDOBLE', 'Doble Prueba')
        cls.doble_b = cls.env['safra.fabric.color'].create(
            {'fabric_id': cls.tela_b.id, 'product_tmpl_id': cls.doble.product_tmpl_id.id})

    def test_producto_archiva_y_reactiva_sus_lineas(self):
        manual = self.env['safra.fabric.color'].create(
            {'fabric_id': self.tela_b.id, 'product_tmpl_id': self.solo.product_tmpl_id.id, 'active': False})
        self.solo.product_tmpl_id.action_archive()
        self.assertFalse(self.solo.active)
        self.assertEqual(self.solo.archivado_por, 'producto')
        self.solo.product_tmpl_id.action_unarchive()
        self.assertTrue(self.solo.active)
        self.assertFalse(self.solo.archivado_por)
        # La que se archivó a mano en Referencias no se reactiva.
        self.assertFalse(manual.active)

    def test_linea_archiva_el_producto_si_no_queda_en_otra(self):
        self.solo.action_archive()
        self.assertFalse(self.solo.product_tmpl_id.active)
        self.solo.action_unarchive()
        self.assertTrue(self.solo.product_tmpl_id.active)
        # Sigue activo en la referencia B: el producto no se toca.
        self.doble.action_archive()
        self.assertTrue(self.doble.product_tmpl_id.active)
        self.doble_b.action_archive()
        self.assertFalse(self.doble.product_tmpl_id.active)

    def test_referencia_archiva_sus_lineas(self):
        self.tela_b.action_archive()
        self.assertFalse(self.doble_b.active)
        self.assertEqual(self.doble_b.archivado_por, 'referencia')
        self.assertTrue(self.doble.product_tmpl_id.active)  # sigue en la referencia de prueba
        self.tela_b.action_unarchive()
        self.assertTrue(self.doble_b.active)

    def test_ajuste_de_los_datos_existentes(self):
        self.solo.product_tmpl_id.with_context(safra_sync_activo=True).write({'active': False})
        self.assertTrue(self.solo.active)
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'website_quotes_safra.ajuste_activo_productos')]).unlink()
        self.env['safra.fabric.color']._ajuste_activo_productos()
        self.assertFalse(self.solo.active)
        self.assertEqual(self.solo.archivado_por, 'producto')
