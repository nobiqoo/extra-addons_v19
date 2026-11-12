# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestReglasModulo(SafraCommon):
    """Revisión 3-nov: las reglas que trae el módulo no se borran desde la
    pantalla (se desactivan) y una condición que falla en el portal queda
    marcada en la regla."""

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.Rule = self.env['safra.validation.rule']

    def test_la_del_modulo_no_se_borra_solo_se_desactiva(self):
        regla = self.Rule.create({'code': 'ZT_MODULO', 'name': 'Del módulo', 'condition_code': 'ancho > 9'})
        self.assertTrue(regla.del_modulo)
        with self.assertRaisesRegex(UserError, 'No se pueden borrar reglas del módulo'):
            regla.with_user(self.admin).unlink()
        regla.with_user(self.admin).active = False
        self.assertFalse(regla.active)

    def test_la_de_pantalla_si_se_borra(self):
        regla = self.Rule.with_user(self.admin).create(
            {'code': 'ZT_PROPIA', 'name': 'Propia', 'condition_code': 'ancho > 9'})
        self.assertFalse(regla.del_modulo)
        regla.unlink()
        self.assertFalse(regla.exists())

    def test_ajuste_marca_las_existentes(self):
        regla = self.Rule.create({'code': 'ZT_VIEJA', 'name': 'Vieja', 'condition_code': 'ancho > 9'})
        regla.del_modulo = False
        self.Rule._ajuste_reglas_del_modulo()
        self.assertTrue(regla.del_modulo)
        # Las sembradas por el módulo quedan marcadas.
        self.assertTrue(self.Rule._por_clave(['V_ANCHO_ROLLO']).del_modulo)

    def test_condicion_con_error_queda_en_la_regla(self):
        # Pasa la revisión al guardar (falla solo con los datos de una persiana).
        regla = self.Rule.create({'code': 'ZT_FALLA', 'name': 'Falla', 'momento': 'linea',
                                  'condition_code': 'result = 1 / (ancho - 1.5) > 0'})
        self.assertNotIn('ZT_FALLA', self.codigos([self.linea(width=1.5)], cross=False))
        self.assertIn('division by zero', regla.ultimo_error)
        self.assertTrue(regla.ultimo_error_fecha)
        # Con otro ancho la regla vuelve a revisarse; el aviso sigue hasta corregirla.
        self.assertIn('ZT_FALLA', self.codigos([self.linea(width=2.0)], cross=False))
        self.assertTrue(regla.ultimo_error)
        regla.condition_code = 'result = ancho > 1.5'
        self.assertFalse(regla.ultimo_error)
        self.validar([self.linea(width=1.5)], cross=False)
        self.assertFalse(regla.ultimo_error)

    def test_quitar_aviso_de_error(self):
        regla = self.Rule.create({'code': 'ZT_FALLA2', 'name': 'Falla', 'momento': 'linea',
                                  'condition_code': 'result = 1 / (ancho - 1.5) > 0'})
        self.validar([self.linea(width=1.5)], cross=False)
        self.assertTrue(regla.ultimo_error)
        regla.action_limpiar_error()
        self.assertFalse(regla.ultimo_error)
        self.assertFalse(regla.ultimo_error_fecha)
