# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestEstructura(SafraCommon):
    """Estructura por ancho, alto y peso máximo, mecanismo y Unificación
    Mando (Sprint 1.2 y 1.3)."""

    def setUp(self):
        super().setUp()
        self.Rule = self.env['safra.structure.rule']

    def test_regla_por_ancho_y_accionamiento(self):
        self.assertEqual(self.Rule.find_rule(self.enrollable, 1.5), self.r8_manual)
        self.assertEqual(self.Rule.find_rule(self.enrollable, 1.5, motorized=True), self.r8_motor)
        self.assertEqual(self.Rule.find_rule(self.enrollable, 2.4), self.r16)
        self.assertEqual(self.Rule.find_rule(self.enrollable, 2.8, motorized=True), self.r24)
        self.assertFalse(self.Rule.find_rule(self.enrollable, 3.5))

    def test_regla_por_cabezal(self):
        self.assertEqual(self.Rule.find_rule(self.enrollable, 1.5, cabezal='redondo'),
                         self.r8_redondo)
        # Sin regla propia del cabezal cuadrado se usa la general.
        self.assertEqual(self.Rule.find_rule(self.enrollable, 1.5, cabezal='cuadrado'),
                         self.r8_manual)

    def test_linea_de_mecanismo(self):
        """Sprint 1.3 (fila 71): el cabezal es el elegido o «No aplica».
        Reunión 15-oct (fila 69): sin Soporte ni Terminal."""
        self.assertEqual(self.r8_manual._mechanism_line(),
                         'Tubo: R8 - Mecanismo: R8SL - Cabezal: No aplica')
        self.assertTrue(self.r8_manual._mechanism_line('Cabezal Redondo').endswith(
            'Cabezal: Cabezal Redondo'))

    def test_alto_y_peso_maximo(self):
        """Alto máximo = el menor entre el que cabe por espacio y el que
        soporta la carga; peso = ancho × alto × peso tela × factor + perfil."""
        lim = self.r8_manual.compute_limits(2.0, 2.0, peso_tela=300, grosor_tela=0.5,
                                            peso_perfil=100)
        # Espacio: ((60 − 20) / 0,5) × π × 40 / 1000 = 10,05 m.
        # Carga: (2000 − 2 × 100) / (300 × 2) = 3,00 m.
        self.assertEqual(lim['alto_maximo'], 3.0)
        self.assertEqual(lim['alto_limitante'], 'carga')
        self.assertEqual(lim['peso_total'], 1400)
        self.assertTrue(lim['alto_ok'])
        self.assertTrue(lim['peso_ok'])
        # Sheer: la tela va doblada (factor 2).
        sheer = self.r8_manual.compute_limits(2.0, 2.0, peso_tela=300, grosor_tela=0.5,
                                              peso_perfil=100, factor=2)
        self.assertEqual(sheer['alto_maximo'], 1.5)
        self.assertFalse(sheer['alto_ok'])
        self.assertFalse(sheer['peso_ok'])

    def test_sin_parametros_no_hay_limite(self):
        lim = self.r16.compute_limits(2.4, 2.0)
        self.assertIsNone(lim['alto_maximo'])
        self.assertIsNone(lim['alto_ok'])

    def test_tubos_ordenados(self):
        self.assertEqual(self.Rule.tubos_ordenados(self.enrollable), ['R8', 'R16', 'R24'])

    def test_unificacion_mando(self):
        """Pedir un tubo mayor cambia la regla efectiva; uno menor, igual o
        desconocido no cambia nada."""
        base, efectiva = self.Rule.resolve(self.enrollable, 1.5, unificacion='R16')
        self.assertEqual((base, efectiva), (self.r8_manual, self.r16))
        for pedido in ('R8', 'R99', None):
            self.assertEqual(self.Rule.resolve(self.enrollable, 1.5, unificacion=pedido),
                             (self.r8_manual, self.r8_manual))
        self.assertEqual(self.Rule.resolve(self.enrollable, 2.4, unificacion='R8'),
                         (self.r16, self.r16))

    def test_unificacion_en_secuencia(self):
        """En una secuencia todas las persianas toman el tubo mayor; la
        línea queda con la Unificación Mando y así se guarda."""
        lineas = [
            self.linea(width=1.5, same_header=True, sequence_name='S1',
                       soporte_izq='MANDO', soporte_der='DEP'),
            self.linea(width=2.4, same_header=True, sequence_name='S1',
                       soporte_izq='DEP', soporte_der='TERMINAL'),
        ]
        self.validar(lineas)
        self.assertEqual(lineas[0]['attribute_values'].get('unificacion_mando'), 'R16')
        self.assertNotIn('unificacion_mando', lineas[1]['attribute_values'])

    def test_unificacion_mayor_en_secuencia(self):
        """Reunión 15-oct (fila 73): en secuencia se puede pedir un tubo
        mayor al calculado y se aplica a todas; uno menor no cuenta."""
        lineas = [
            self.linea(width=1.5, same_header=True, sequence_name='S1',
                       soporte_izq='MANDO', soporte_der='DEP'),
            self.linea(width=2.4, same_header=True, sequence_name='S1',
                       soporte_izq='DEP', soporte_der='TERMINAL',
                       attribute_values={'unificacion_mando': 'R24'}),
        ]
        self.validar(lineas)
        self.assertEqual([l['attribute_values'].get('unificacion_mando') for l in lineas],
                         ['R24', 'R24'])
        menor = [
            self.linea(width=1.5, same_header=True, sequence_name='S2',
                       soporte_izq='MANDO', soporte_der='DEP'),
            self.linea(width=2.4, same_header=True, sequence_name='S2',
                       soporte_izq='DEP', soporte_der='TERMINAL',
                       attribute_values={'unificacion_mando': 'R8'}),
        ]
        self.validar(menor)
        self.assertEqual(menor[0]['attribute_values'].get('unificacion_mando'), 'R16')
        self.assertNotIn('unificacion_mando', menor[1]['attribute_values'])
