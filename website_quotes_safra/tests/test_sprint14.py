# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestSprint14(SafraCommon):
    """Sprint 1.4 (filas 79-96 de la matriz): Diseño de impresión, Cenefa y
    Perfil Cover Light. La función se vuelve a aplicar aquí, así el
    resultado no depende de lo que el funcional haya cambiado en la base."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Field = cls.env['safra.field'].with_context(active_test=False)
        # Las condiciones de cenefa que editó el funcional se respetan (ver
        # test_respeta_las_condiciones_de_safra): se vacían para probar lo
        # que siembra el módulo.
        cls.Field.search([('code', 'in', list(cls.Field.SPRINT14_DEPENDS))]).write(
            {'depends_field_id': False, 'depends_value': False})
        cls.env['safra.system.field'].with_context(active_test=False).search([
            ('field_id.code', 'in', ['cenefa_lined', 'cenefa_tela'])]).write(
            {'depends_field_id': False, 'depends_value': False})
        cls.Field._apply_sprint14()

    def campo(self, code):
        return self.Field.search([('code', '=', code)], limit=1)

    def mapeo(self, code, sistema):
        return self.env['safra.system.field'].with_context(active_test=False).search([
            ('field_id.code', '=', code), ('system_id.code', '=', sistema)], limit=1)

    def activos(self, code):
        mappings = self.env['safra.system.field'].search([('field_id.code', '=', code)])
        return set(mappings.mapped('system_id.code')) - {'ZT01', 'ZT11'}

    def test_sistemas_como_la_matriz(self):
        Field = self.env['safra.field']
        existentes = set(self.env['safra.system'].with_context(active_test=False).search([]).mapped('code'))
        for code, sistemas in Field.SPRINT14_SISTEMAS.items():
            with self.subTest(campo=code):
                self.assertEqual(self.activos(code), set(sistemas) & existentes)

    def test_catalogo_de_disenos_donde_hay_diseno(self):
        """El error del 17-sep: Diseño Impresión sin catálogo bloqueaba."""
        self.assertEqual(self.activos('design_print'), self.activos('custom_design'))

    def test_sobrantes_se_archivan(self):
        sobrante = self.mapeo('corte_cenefa', '01')
        if sobrante:
            self.assertFalse(sobrante.active)
            self.assertTrue(sobrante.exists())

    def test_tipo_de_cenefa_por_referencias(self):
        tipo = self.campo('cenefa_panel')
        self.assertEqual(tipo.field_type, 'ref_categoria')
        self.assertEqual(tipo.ref_category_id.name, 'Cenefa')

    def test_dependencias(self):
        self.assertEqual((self.campo('perfil_cenefa').depends_field_id.code,
                          self.campo('perfil_cenefa').depends_value),
                         ('cenefa_panel', self.Field._S14_TELA))
        self.assertEqual(self.campo('cenefa_longitud').depends_value, 'izquierdo,derecho,ambos')
        # Reunión 20-oct: el Cover Light viene de Referencias, se compara la etiqueta.
        self.assertEqual(self.campo('coverlight_felpa').depends_value,
                         'dos_laterales_5cm,eti:2 lateral,eti:2 laterales')
        self.assertEqual(self.campo('coverlight_45').depends_value,
                         'tres_laterales_5cm,eti:3 lateral,eti:3 laterales')
        # En los paneles la forrada va con la cenefa metálica.
        panel = self.mapeo('cenefa_lined', '11')
        if panel:
            self.assertEqual(panel.depends_value, self.Field._S14_MET)
        # Sin forrada en el sistema, la tela de la cenefa va con la cenefa en tela.
        romana = self.mapeo('cenefa_tela', '10')
        if romana:
            self.assertEqual((romana.depends_field_id.code, romana.depends_value),
                             ('cenefa_panel', self.Field._S14_TELA))
        # Ninguna dependencia apunta a un campo archivado («Cenefa PVC»).
        codes = list(self.env['safra.field'].SPRINT14_SISTEMAS)
        mappings = self.env['safra.system.field'].search([('field_id.code', 'in', codes)])
        self.assertFalse(mappings.filtered(
            lambda m: m.depends_field_id and not m.depends_field_id.active))

    def test_respeta_las_condiciones_de_safra(self):
        """Reunión 15-oct: una actualización no pisa las condiciones que
        Safra escribió con sus códigos (una referencia, atributos por
        clase); sí reemplaza las que dejaron versiones anteriores."""
        lateral, perfil = self.campo('cenefa_lateral'), self.campo('perfil_cenefa')
        lateral.depends_value = '054328,I100003005'
        perfil.depends_value = '2,4,5,6'
        panel = self.mapeo('cenefa_lined', '11')
        if panel:
            panel.depends_value = '2815'
        self.Field._apply_sprint14()
        self.assertEqual(lateral.depends_value, '054328,I100003005')
        self.assertEqual(perfil.depends_value, self.Field._S14_TELA)
        if panel:
            self.assertEqual(panel.depends_value, '2815')

    def test_opciones_de_cenefa_por_sistema(self):
        romana = self.mapeo('cenefa_panel', '10')
        if romana:
            self.assertEqual(romana.option_ids.mapped('name'), ['Sin Cenefa', 'Cenefa Tela'])
        panel = self.mapeo('cenefa_panel', '11')
        if panel:
            # Sin copia propia: usa las del campo (formas de tela y metálica).
            self.assertFalse(panel.option_ids)

    def test_nombres_sin_pvc(self):
        for code in ('cenefa_lateral', 'cenefa_lined', 'cenefa_tela', 'cenefa_dividida'):
            self.assertNotIn('PVC', self.campo(code).name)

    def test_idempotente(self):
        self.Field._apply_sprint14()
        romana = self.mapeo('cenefa_panel', '10')
        if romana:
            self.assertEqual(len(romana.option_ids), 2)
        self.test_sistemas_como_la_matriz()
