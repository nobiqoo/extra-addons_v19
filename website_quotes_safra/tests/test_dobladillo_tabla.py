# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import SafraCommon
from ..models import safra_reglas_17 as R17


@tagged('post_install', '-at_install', 'safra')
class TestDobladilloTabla(SafraCommon):
    """Revisión 30-oct (Dobladillo o Bajo falso): cada dobladillo tiene su
    consumo; la lista muestra el alto máximo de la cortina con cada uno y si
    aplica con el alto pedido. Rollo de 2,50 m: alto máximo = 2,50 + 0,035
    (riel) − 0,06 (dobladillo superior) − consumo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Param = cls.env['ir.config_parameter'].sudo()
        for clave, valor in (('safra.cortina.dobladillo_superior', '0.06'),
                             ('safra.cortina.dobladillo_inferior_max', '0.21'),
                             ('safra.cortina.riel', '0.035'),
                             ('safra.cortina.tolerancia_bajo_falso', '0.12')):
            Param.set_param(clave, valor)
        # Las fórmulas del corte como las deja el módulo.
        Param.search([('key', 'in', list(R17.FORMULAS_CORTE_CORTINA))]).unlink()
        cls.cortina = cls._sistema('ZT49D', 'PRUEBA CORTINA DOBLADILLO',
                                   ['width', 'height', 'quantity', 'location', 'fabric_id',
                                    'color_id', 'bajofalso'], (0.30, 11.8, 0.30, 5.0))
        cls.cortina.write({'calculo_corte': 'cortina', 'factor_confeccion': 2.8})
        cls.tela.system_ids = [(4, cls.cortina.id)]
        mapping = cls.env['safra.system.field'].search([
            ('system_id', '=', cls.cortina.id), ('field_id.code', '=', 'bajofalso')])
        falso = R17.DOBLADILLO_CORTE['BN_FALSO']
        cls.env['safra.system.field.option'].create([
            dict({'system_field_id': mapping.id, 'value': valor, 'name': nombre}, **extra)
            for valor, nombre, extra in (
                ('BN_FLTE', 'Bajo filete', {'consumo_dobladillo': 0.06, 'formula': R17.DOBLADILLO_30OCT}),
                ('BN_03', 'Dobladillo de 3 cm', {'consumo_dobladillo': 0.07, 'formula': R17.DOBLADILLO_30OCT}),
                ('BN_10', 'Dobladillo de 10 cm', {'consumo_dobladillo': 0.15, 'formula': R17.DOBLADILLO_30OCT}),
                ('BN_15', 'Dobladillo de 15 cm', {'consumo_dobladillo': 0.21, 'formula': R17.DOBLADILLO_30OCT}),
                ('BN_FALSO', 'Bajo falso', {'formula': falso[0], 'auto_formula': falso[1]}),
            )])

    def formulas(self, alto):
        return self.Line.new({'system_id': self.cortina.id, 'fabric_id': self.tela.id,
                              'color_id': self.blanco.id, 'width': 2.0, 'height': alto,
                              'quantity': 1, 'attribute_values': {}})._formulas_opciones()

    def test_alto_maximo_por_dobladillo(self):
        res = self.formulas(2.0)
        self.assertEqual(res['maximos']['bajofalso'],
                         {'BN_FLTE': 2.415, 'BN_03': 2.405, 'BN_10': 2.325, 'BN_15': 2.265})
        # Alto 2,00: caben todos; el bajo falso no.
        self.assertEqual(res['opciones']['bajofalso'], ['BN_FLTE', 'BN_03', 'BN_10', 'BN_15'])

    def test_solo_los_dobladillos_que_alcanzan(self):
        """Alto 2,40: filete (2,415) y 3 cm (2,405) Sí; 10 y 15 cm No. El
        corte es normal (cabe con el que menos consume)."""
        res = self.formulas(2.4)
        self.assertEqual(res['opciones']['bajofalso'], ['BN_FLTE', 'BN_03'])
        self.assertNotIn('bajofalso', res['auto'])
        linea = self.Line.new({'system_id': self.cortina.id, 'fabric_id': self.tela.id,
                               'color_id': self.blanco.id, 'width': 2.0, 'height': 2.4})
        self.assertEqual(linea._corte_tela()['tipo'], 'normal')

    def test_ninguno_alcanza_bajo_falso(self):
        """Alto 2,45: ningún dobladillo alcanza; hasta 2,62 (rollo + 12 cm)
        es bajo falso y se elige solo."""
        res = self.formulas(2.45)
        self.assertEqual(res['opciones']['bajofalso'], ['BN_FALSO'])
        self.assertEqual(res['auto']['bajofalso'], 'BN_FALSO')

    def test_con_panos_aplican_todos(self):
        self.tela.is_anadido = True
        res = self.formulas(3.0)
        self.assertEqual(res['opciones']['bajofalso'], ['BN_FLTE', 'BN_03', 'BN_10', 'BN_15'])

    def test_el_consumo_se_cambia_en_la_opcion(self):
        opt = self.env['safra.system.field.option'].search([
            ('system_field_id.system_id', '=', self.cortina.id), ('value', '=', 'BN_10')])
        opt.consumo_dobladillo = 0.05
        res = self.formulas(2.4)
        self.assertEqual(res['maximos']['bajofalso']['BN_10'], 2.425)
        self.assertIn('BN_10', res['opciones']['bajofalso'])

    def test_sin_consumos_usa_el_maximo_de_ajustes(self):
        """Sin consumos en las opciones, el corte normal usa el dobladillo
        inferior máximo de Ajustes (0,21): 2,40 + 0,06 + 0,21 − 0,035 > 2,50."""
        self.env['safra.system.field.option'].search([
            ('system_field_id.system_id', '=', self.cortina.id)]).consumo_dobladillo = 0
        linea = self.Line.new({'system_id': self.cortina.id, 'fabric_id': self.tela.id,
                               'color_id': self.blanco.id, 'width': 2.0, 'height': 2.4})
        self.assertEqual(linea._corte_tela()['tipo'], 'bajo_falso')

    def linea(self, alto):
        return self.Line.new({'system_id': self.cortina.id, 'fabric_id': self.tela.id,
                              'color_id': self.blanco.id, 'width': 2.0, 'height': alto})

    def test_formula_del_alto_maximo_en_ajustes(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('safra.formula.alto_maximo_dobladillo', 'result = ancho_rollo - consumo')
        res = self.formulas(2.4)
        self.assertEqual(res['maximos']['bajofalso']['BN_FLTE'], 2.44)
        self.assertEqual(res['opciones']['bajofalso'], ['BN_FLTE', 'BN_03'])
        # Restando 2 cm más: filete 2,42 y 3 cm 2,41; con 2,415 solo alcanza el filete.
        Param.set_param('safra.formula.alto_maximo_dobladillo', 'result = ancho_rollo - consumo - 0.02')
        self.assertEqual(self.formulas(2.4)['opciones']['bajofalso'], ['BN_FLTE', 'BN_03'])
        self.assertEqual(self.formulas(2.415)['opciones']['bajofalso'], ['BN_FLTE'])

    def test_formulas_de_corte_normal_y_bajo_falso_en_ajustes(self):
        Param = self.env['ir.config_parameter'].sudo()
        self.assertEqual(self.linea(2.6)._corte_tela()['tipo'], 'bajo_falso')
        # El bajo falso ahora alcanza solo 5 cm sobre el rollo.
        Param.set_param('safra.formula.cortina_bajo_falso',
                        'result = alto <= ancho_rollo + 0.05 and not tela_con_diseno')
        self.assertEqual(self.linea(2.6)._corte_tela()['tipo'], 'no_fabricable')
        # Corte normal con un margen propio.
        Param.set_param('safra.formula.cortina_normal', 'result = alto <= ancho_rollo')
        self.assertEqual(self.linea(2.5)._corte_tela()['tipo'], 'normal')
        # Vacía vuelve a la del módulo.
        Param.set_param('safra.formula.cortina_normal', False)
        self.assertEqual(self.linea(2.5)._corte_tela()['tipo'], 'bajo_falso')

    def test_formula_con_campo_del_cotizador(self):
        """Lo que la revisión al guardar acepta (campos del cotizador por su
        código) también llega al calcular."""
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('safra.formula.cortina_normal',
                        "result = alto <= alto_maximo_dobladillo and location != 'Patio'")
        linea = self.Line.new({'system_id': self.cortina.id, 'fabric_id': self.tela.id,
                               'color_id': self.blanco.id, 'width': 2.0, 'height': 2.0,
                               'location': 'Sala'})
        self.assertEqual(linea._corte_tela()['tipo'], 'normal')
        linea.location = 'Patio'
        self.assertEqual(linea._corte_tela()['tipo'], 'bajo_falso')

    def test_ajustes_muestran_y_revisan_las_formulas(self):
        Settings = self.env['res.config.settings']
        ajustes = Settings.create({})
        self.assertEqual(ajustes.safra_formula_cortina_normal,
                         R17.FORMULAS_CORTE_CORTINA['safra.formula.cortina_normal'])
        ajustes.safra_formula_cortina_normal = 'result = alto <= rollo'
        with self.assertRaisesRegex(ValidationError, 'No existe la variable «rollo»'):
            ajustes.execute()
        ajustes = Settings.create({'safra_formula_cortina_normal': 'result = alto <= ancho_rollo - 0.1'})
        ajustes.execute()
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param('safra.formula.cortina_normal'),
                         'result = alto <= ancho_rollo - 0.1')

    def test_ajuste_pone_consumos_y_formula(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.search([('key', '=', 'website_quotes_safra.ajuste_dobladillo_consumo')]).unlink()
        campo = self._campo('bajofalso')
        Option = self.env['safra.field.option']
        anterior = R17.DOBLADILLO_CORTE['BN_FLTE'][0]
        for valor in ('BN_FLTE', 'BN_10'):
            opt = campo.option_ids.filtered(lambda o: o.value == valor)[:1] or Option.create(
                {'field_id': campo.id, 'value': valor, 'name': valor})
            opt.write({'consumo_dobladillo': 0, 'formula': anterior})
        propia = campo.option_ids.filtered(lambda o: o.value == 'BN_10')
        propia.formula = 'result = alto < 2'
        self.env['safra.validation.rule']._ajuste_dobladillo_consumo()
        filete = campo.option_ids.filtered(lambda o: o.value == 'BN_FLTE')
        self.assertEqual((filete.consumo_dobladillo, filete.formula), (0.06, R17.DOBLADILLO_30OCT))
        # La fórmula que se cambió a mano se respeta; el consumo sí se pone.
        self.assertEqual((propia.consumo_dobladillo, propia.formula), (0.15, 'result = alto < 2'))


@tagged('post_install', '-at_install', 'safra')
class TestCalculoCorteOtro(SafraCommon):

    def test_otro_no_tiene_calculo(self):
        self.enrollable.calculo_corte = 'otro'
        corte = self.Line.new(self.linea(width=2.6))._corte_tela()
        self.assertEqual(corte['tipo'], '')

    def test_ajuste_deja_en_otro_los_que_faltan(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.search([('key', '=', 'website_quotes_safra.ajuste_calculo_corte_otro')]).unlink()
        self.enrollable.calculo_corte = False
        self.panel.calculo_corte = 'persiana'
        self.env['safra.system']._ajuste_calculo_corte_otro()
        self.assertEqual((self.enrollable.calculo_corte, self.panel.calculo_corte), ('otro', 'persiana'))

    def test_obligatorio_en_el_formulario(self):
        """El desplegable es obligatorio en el producto marcado como sistema
        y en el formulario del sistema."""
        vista = self.env.ref('website_quotes_safra.product_template_form_parametrizacion')
        self.assertIn('name="safra_calculo_corte" invisible="not safra_is_system" '
                      'required="safra_is_system"', vista.arch_db)
