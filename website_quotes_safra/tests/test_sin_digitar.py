# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon
from ..models.safra_panel import datos_usados, evaluar_formula


@tagged('post_install', '-at_install', 'safra')
class TestFormulasSinDigitar(SafraCommon):
    """9-nov: las fórmulas distinguen un dato del maestro sin digitar del
    digitado en 0 y avisan cuando usan un dato vacío."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sin_ancho = cls._color(cls.tela, 'ZTVAC', 'Vacío Prueba')
        cls.sin_ancho.product_tmpl_id.safra_u_ancho = False
        cls.cero = cls._color(cls.tela, 'ZTCER', 'Cero Prueba', ancho_rollo=0.0)
        cls.regla = cls.env['safra.validation.rule'].create({
            'code': 'R_ROLLO_PRUEBA', 'name': 'Ancho mayor que el rollo', 'momento': 'linea',
            'severity': 'error', 'condition_code': 'bool(ancho_rollo) and ancho > ancho_rollo',
            'message': 'Supera el rollo'})

    def test_funcion_vacio_en_las_formulas(self):
        self.assertTrue(evaluar_formula('vacio(x)', {'x': False})[0])
        self.assertFalse(evaluar_formula('vacio(x)', {'x': 0.0})[0])
        self.assertEqual(datos_usados('bool(ancho_rollo) and ancho > 2'), {('bool',), ('ancho_rollo',), ('ancho',)})

    def test_ancho_rollo_vacio_y_cero(self):
        self.enrollable.calculo_corte = 'persiana'
        vacia = self.env['safra.quote.line'].new(self.linea(color_id=self.sin_ancho.id))
        cero = self.env['safra.quote.line'].new(self.linea(color_id=self.cero.id))
        self.assertIs(vacia._ancho_rollo(), False)
        self.assertEqual(cero._ancho_rollo(), 0.0)
        self.assertIn('ancho_rollo', vacia._sin_digitar()['variables'])
        self.assertNotIn('ancho_rollo', cero._sin_digitar()['variables'])
        self.assertIn('no tiene digitado', vacia._corte_tela()['motivo'])
        self.assertIn('en 0', cero._corte_tela()['motivo'])

    def test_aviso_de_la_formula_que_usa_el_dato_vacio(self):
        avisos = [a for a in self.mensajes([self.linea(color_id=self.sin_ancho.id)], 'V_DATO_SIN_DIGITAR')
                  if 'U_Ancho' in a['message']]
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['severity'], 'warning')
        self.assertIn('U_Ancho del color Vacío Prueba', avisos[0]['message'])
        self.assertIn('la validación «Ancho mayor que el rollo»', avisos[0]['message'])
        # Con el 0 digitado no hay aviso: el dato existe.
        self.assertFalse([a for a in self.mensajes([self.linea(color_id=self.cero.id)], 'V_DATO_SIN_DIGITAR')
                          if 'U_Ancho' in a['message']])

    def test_aviso_desde_validaciones(self):
        """Revisión 10-nov: el aviso es la regla V_DATO_SIN_DIGITAR de
        Validaciones, con su condición escrita (datos_sin_digitar): Safra
        cambia la severidad, el mensaje o la condición, o la apaga."""
        Rule = self.env['safra.validation.rule'].with_context(active_test=False)
        regla = Rule.search([('code', '=', 'V_DATO_SIN_DIGITAR')])
        self.assertEqual((len(regla), regla.severity), (1, 'warning'))
        self.assertIn('datos_sin_digitar', regla.condition_code)
        self.assertNotIn('hallazgo', regla.condition_code)
        linea = [self.linea(color_id=self.sin_ancho.id)]
        regla.write({'severity': 'error', 'message': 'Digite en el maestro: {faltan}.'})
        avisos = [a for a in self.mensajes(linea, 'V_DATO_SIN_DIGITAR') if 'U_Ancho' in a['message']]
        self.assertEqual(avisos[0]['severity'], 'error')
        self.assertTrue(avisos[0]['message'].startswith('Digite en el maestro: U_Ancho del color Vacío Prueba'))
        # Con una condición propia: solo los datos que usa una validación.
        regla.condition_code = (
            "faltan = ', '.join([d['dato'] for d in datos_sin_digitar if 'validación' in d['usos']])\n"
            "result = bool(faltan)")
        self.assertTrue([a for a in self.mensajes(linea, 'V_DATO_SIN_DIGITAR') if 'U_Ancho' in a['message']])
        regla.condition_code = (
            "faltan = ', '.join([d['dato'] for d in datos_sin_digitar if 'Ajustes' in d['usos']])\n"
            "result = bool(faltan)")
        self.assertFalse([a for a in self.mensajes(linea, 'V_DATO_SIN_DIGITAR') if 'U_Ancho' in a['message']])
        # Apagada, no sale.
        regla.active = False
        self.assertFalse(self.mensajes(linea, 'V_DATO_SIN_DIGITAR'))

    def nueva_regla(self, code, nombre, condicion, mensaje):
        return self.env['safra.validation.rule'].create({
            'code': code, 'name': nombre, 'momento': 'linea', 'severity': 'error',
            'condition_code': condicion, 'message': mensaje})

    def avisos_de(self, lineas, texto):
        return [a['message'] for a in self.mensajes(lineas, 'V_DATO_SIN_DIGITAR') if texto in a['message']]

    def test_dato_que_la_validacion_lee_de_un_registro(self):
        # Cualquier número del maestro, no solo U_Ancho: aquí el peso de la referencia.
        self.nueva_regla('R_PESO_PRUEBA', 'Tela muy pesada', 'tela.peso_gm2 > 500', 'Muy pesada')
        self.tela.peso_gm2 = False
        avisos = self.avisos_de([self.linea()], 'la validación «Tela muy pesada»')
        self.assertEqual(len(avisos), 1)
        self.assertIn('Falta digitar Peso tela (g/m²) de la referencia', avisos[0])
        self.tela.peso_gm2 = 0
        self.assertFalse(self.avisos_de([self.linea()], 'la validación «Tela muy pesada»'))

    def test_limites_de_la_ficha_sin_digitar(self):
        self.nueva_regla('R_WMAX_PRUEBA', 'Ancho de la ficha', "ancho > limites['wmax']",
                   'Supera el máximo de {limites[wmax]:.2f} m')
        self.enrollable.tech_width_max = False
        self.enrollable.product_tmpl_id.safra_u_ancho_max = False
        linea = self.Line.new(self.linea())
        self.assertIs(linea._contexto_reglas(1)['limites']['wmax'], False)
        # El mensaje dice «sin digitar», no «False».
        self.assertEqual([m['message'] for m in self.mensajes([self.linea()], 'R_WMAX_PRUEBA')],
                         ['Supera el máximo de sin digitar m'])
        avisos = self.avisos_de([self.linea()], 'la validación «Ancho de la ficha»')
        self.assertEqual(len(avisos), 1)
        self.assertIn('Ancho máximo (m) del sistema', avisos[0])
        # Digitado en 0 en el sistema: ya no está vacío.
        self.enrollable.tech_width_max = 0
        self.assertFalse(self.avisos_de([self.linea()], 'la validación «Ancho de la ficha»'))

    def test_formulas_del_tubo(self):
        self.tela.write({'peso_gm2': False, 'grosor_mm': 0.4})
        linea = self.Line.new(self.linea())
        regla = linea._estructura_linea()[1]
        self.assertTrue(regla)
        params = linea._params_estructura()
        self.assertIs(params['peso_tela'], False)
        self.assertIs(regla._ctx_limites(1.5, 1.8, **params)['peso_tela'], False)
        formulas = linea._sin_digitar()['formulas']
        dato = [d for d in formulas if d.startswith('Peso tela (g/m²) de la referencia')]
        self.assertEqual(len(dato), 1)
        self.assertIn('la fórmula «Alto máximo por carga» de Ajustes › Tubo', formulas[dato[0]])
        self.tela.peso_gm2 = 0
        self.assertFalse([d for d in linea._sin_digitar()['formulas'] if d.startswith('Peso tela')])

    def test_rutas_que_lee_una_formula(self):
        rutas = datos_usados("tela.peso_gm2 > 1 and limites['wmax'] and estructura.get('aumento_tela', 0)")
        self.assertIn(('tela', 'peso_gm2'), rutas)
        self.assertIn(('limites', "['wmax']"), rutas)
        self.assertIn(('estructura', "['aumento_tela']"), rutas)
