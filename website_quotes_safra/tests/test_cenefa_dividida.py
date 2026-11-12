# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestCenefaDividida(SafraCommon):
    """Revisión 27-oct (pruebas de Safra): con Tipo de Cenefa elegido,
    «¿Cenefa dividida?» debe decir Sí o No; sin cenefa no se pide."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['safra.system.field'].create([
            {'system_id': cls.enrollable.id, 'field_id': cls._campo('cenefa_panel').id, 'sequence': 500},
            {'system_id': cls.enrollable.id, 'field_id': cls._campo('cenefa_dividida').id, 'sequence': 510},
        ])

    def avisos(self, **attrs):
        return self.mensajes([self.linea(attribute_values=attrs)], 'V_CENEFA_DIVIDIDA')

    def test_con_cenefa_hay_que_elegir(self):
        self.assertEqual([a['message'] for a in self.avisos(cenefa_panel='2')],
                         ['E13095: Indique si la cenefa va dividida (Sí o No).'])
        self.assertFalse(self.avisos(cenefa_panel='2', cenefa_dividida='0'))  # «No» también vale
        self.assertFalse(self.avisos(cenefa_panel='2', cenefa_dividida='1'))

    def test_sin_cenefa_no_se_pide(self):
        self.assertFalse(self.avisos())
        self.assertFalse(self.avisos(cenefa_dividida=''))

    def test_regla_apagada(self):
        self.env['safra.validation.rule'].search([('code', '=', 'V_CENEFA_DIVIDIDA')]).active = False
        self.assertFalse(self.avisos(cenefa_panel='2'))

    def test_codigo_repetido_en_otro_sistema(self):
        """El código de la cenefa elegida también está en una referencia de
        otro sistema: manda la del sistema de la persiana."""
        Fabric = self.env['safra.fabric']
        Color = self.env['safra.fabric.color']
        categoria = self._campo('cenefa_panel').ref_category_id
        otra = Fabric.create({'code': 'ZT-CEN-OTRA', 'name': 'AAA Cenefas otro sistema',
                              'category_id': categoria.id, 'system_ids': [(6, 0, self.panel.ids)]})
        propia = Fabric.create({'code': 'ZT-CEN', 'name': 'ZZZ Cenefas prueba',
                                'category_id': categoria.id, 'system_ids': [(6, 0, self.enrollable.ids)]})
        Color.create({'fabric_id': otra.id, 'code': 'ZTCEN', 'etiqueta': 'Blanco'})
        Color.create({'fabric_id': propia.id, 'code': 'ZTCEN', 'etiqueta': 'PVC CLASICA'})
        self.assertEqual([a['message'] for a in self.avisos(cenefa_panel='ZTCEN')],
                         ['E13095: Indique si la cenefa va dividida (Sí o No).'])

    def test_codigo_repetido_en_el_mismo_sistema(self):
        """Dos líneas del mismo sistema con el mismo código (p. ej. «Sin
        cenefa» y «PVC CLASICA»): basta con que una muestre el campo."""
        Fabric = self.env['safra.fabric']
        Color = self.env['safra.fabric.color']
        categoria = self._campo('cenefa_panel').ref_category_id
        sin = Fabric.create({'code': 'ZT-SIN-CEN', 'name': 'AAA Sin cenefa prueba',
                             'category_id': categoria.id})
        propia = Fabric.create({'code': 'ZT-CEN', 'name': 'ZZZ Cenefas prueba',
                                'category_id': categoria.id, 'system_ids': [(6, 0, self.enrollable.ids)]})
        Color.create({'fabric_id': sin.id, 'code': 'ZTCEN2', 'etiqueta': 'Blanco'})
        Color.create({'fabric_id': propia.id, 'code': 'ZTCEN2', 'etiqueta': 'PVC CLASICA'})
        self.assertTrue(self.avisos(cenefa_panel='ZTCEN2'))

