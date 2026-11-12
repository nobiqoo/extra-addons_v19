# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestAlineado(SafraCommon):
    """Alineado (revisión 17-sep y reunión 28-sep, fila 13)."""

    def alineada(self, **vals):
        return self.linea(aligned=True, **vals)

    def test_alineada_sola(self):
        codigos = self.codigos([self.alineada()])
        self.assertIn('V_ALINEADO_MIN', codigos)
        self.assertIn('V_ALINEADO_LOCALIZACION', codigos)

    def test_pareja_valida(self):
        self.assertEqual(self.validar([self.alineada(), self.alineada()]), [])

    def test_otra_localizacion(self):
        codigos = self.codigos([self.alineada(), self.alineada(location='Comedor')])
        self.assertIn('V_ALINEADO_LOCALIZACION', codigos)
        self.assertNotIn('V_ALINEADO_MIN', codigos)

    def test_otro_color(self):
        self.assertIn('V_ALINEADO_MIN', self.codigos(
            [self.alineada(), self.alineada(color_id=self.gris.id)]))

    def test_altura_distinta_es_advertencia(self):
        issues = self.mensajes([self.alineada(), self.alineada(height=2.0)], 'V_ALINEADO_ALTURA')
        self.assertEqual([i['severity'] for i in issues], ['warning'])

    def test_altura_distinta_con_franjas_bloquea(self):
        sheer = {'fabric_id': self.tela_sheer.id, 'color_id': self.sheer.id}
        issues = self.mensajes([self.alineada(**sheer), self.alineada(height=2.0, **sheer)],
                               'V_ALINEADO_FRANJAS')
        self.assertEqual([i['severity'] for i in issues], ['error'])

    def test_guardar_persiana_no_corre_reglas_del_pedido(self):
        """«Guardar persiana» valida una sola línea (cross=False)."""
        self.assertEqual(self.validar([self.alineada()], cross=False), [])


@tagged('post_install', '-at_install', 'safra')
class TestSecuencias(SafraCommon):
    """Mismo cabezal y configurador de secuencia (fase 5.4c, 24 y 28-sep)."""

    def persiana(self, izq=None, der=None, nombre='S1', **vals):
        vals = dict({'same_header': True, 'sequence_name': nombre}, **vals)
        if izq:
            vals['soporte_izq'] = izq
        if der:
            vals['soporte_der'] = der
        return self.linea(**vals)

    def test_secuencia_valida(self):
        lineas = [self.persiana('MANDO', 'DEP'), self.persiana('DEP', 'TERMINAL')]
        self.assertEqual(self.validar(lineas), [])

    def test_sin_nombre(self):
        self.assertIn('V_SECUENCIA_NOMBRE', self.codigos(
            [self.persiana('MANDO', 'DEP', nombre=''), self.persiana('DEP', 'TERMINAL', nombre='')]))

    def test_secuencia_de_una_persiana(self):
        self.assertIn('V_SECUENCIA_MIN', self.codigos([self.persiana('MANDO', 'TERMINAL')]))

    def test_sin_configurar(self):
        self.assertIn('V_SECUENCIA_PENDIENTE', self.codigos(
            [self.persiana('MANDO', 'DEP'), self.persiana()]))

    def test_mismo_alto_por_referencia(self):
        self.assertIn('V_SECUENCIA_ALTO', self.codigos(
            [self.persiana('MANDO', 'DEP'), self.persiana('DEP', 'TERMINAL', height=2.0)]))

    def test_reglas_de_soportes(self):
        def mensajes(*sops):
            return [i['message'] for i in self.mensajes(
                [self.persiana(i, d) for i, d in sops], 'V_SECUENCIA')]
        # Dos tracciones unidas por soportes dependientes.
        self.assertTrue(any('Conflicto de tracción' in m
                            for m in mensajes(('MANDO', 'DEP'), ('DEP', 'MANDO'))))
        # Unidas por dependientes sin ninguna tracción.
        self.assertTrue(any('Falta una fuente de tracción' in m
                            for m in mensajes(('TERMINAL', 'DEP'), ('DEP', 'TERMINAL'))))
        # La secuencia no puede empezar con un dependiente.
        self.assertTrue(any('no puede iniciar ni terminar' in m
                            for m in mensajes(('DEP', 'DEP'), ('DEP', 'MANDO'))))
        # Los soportes que se enfrentan deben coincidir.
        self.assertTrue(any('deben coincidir' in m
                            for m in mensajes(('MANDO', 'DEP'), ('INDEP', 'TERMINAL'))))
        # Dos tracciones enfrentadas entre vecinas.
        self.assertTrue(any('enfrentadas' in m
                            for m in mensajes(('TERMINAL', 'MANDO'), ('MOTOR', 'TERMINAL'))))


@tagged('post_install', '-at_install', 'safra')
class TestPlanos(SafraCommon):
    """Tipo de Plano y segmentos (bloque 3 y Sprint 1.1): cada plano usado
    debe traer en el pedido todos sus segmentos, una sola vez."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        campo = cls._campo('tipo_plano')
        cls.env['safra.field.option'].create([
            {'field_id': campo.id, 'value': 'ZP2', 'name': 'Plano prueba 2', 'segmentos': 2},
            {'field_id': campo.id, 'value': 'ZP3', 'name': 'Plano prueba 3', 'segmentos': 3},
        ])

    def con_plano(self, plano, segmento, **vals):
        attrs = {'tipo_plano': plano}
        if segmento:
            attrs['num_segmento'] = segmento
        return self.linea(attribute_values=attrs, **vals)

    def segmentos(self, lineas):
        return [i['message'] for i in self.mensajes(lineas, 'V_PLANO_SEGMENTOS')]

    def test_plano_completo(self):
        self.assertEqual(self.segmentos([self.con_plano('ZP2', '1'), self.con_plano('ZP2', '2')]), [])

    def test_falta_un_segmento(self):
        mensajes = self.segmentos([self.con_plano('ZP3', '1'), self.con_plano('ZP3', '2')])
        self.assertEqual(len(mensajes), 1)
        self.assertIn('falta el 3', mensajes[0])

    def test_segmento_repetido_o_inexistente(self):
        self.assertTrue(any('ya lo usa' in m for m in self.segmentos(
            [self.con_plano('ZP2', '1'), self.con_plano('ZP2', '1'), self.con_plano('ZP2', '2')])))
        self.assertTrue(any('trae el segmento 3' in m for m in self.segmentos(
            [self.con_plano('ZP2', '1'), self.con_plano('ZP2', '3')])))

    def test_sin_segmento(self):
        self.assertTrue(any('falta elegir el Segmento' in m
                            for m in self.segmentos([self.con_plano('ZP2', None)])))

    def test_secuencia_cuenta_como_un_segmento(self):
        secuencia = dict(same_header=True, sequence_name='S1')
        lineas = [
            self.con_plano('ZP2', '1', soporte_izq='MANDO', soporte_der='DEP', **secuencia),
            self.con_plano('ZP2', '1', soporte_izq='DEP', soporte_der='TERMINAL', **secuencia),
            self.con_plano('ZP2', '2'),
        ]
        self.assertEqual(self.segmentos(lineas), [])


@tagged('post_install', '-at_install', 'safra')
class TestControlYCanal(SafraCommon):
    """Control y canal (24-sep, 16.2 y reunión 13-oct, filas 56-57)."""

    def motorizada(self, control=None, canal=None, **vals):
        vals = dict({'has_motor': True, 'motor': 'M1'}, **vals)
        if control is not None:
            vals['control'] = control
        if canal is not None:
            vals['control_channel'] = canal
        return self.linea(**vals)

    @property
    def mono(self):
        return self.ctl_mono._valor_control()

    @property
    def multi(self):
        return self.ctl_multi._valor_control()

    def test_valores_de_las_lineas(self):
        self.assertEqual(self.ctl_sin._valor_control(), '0')
        self.assertEqual(self.multi, 'ref-%d' % self.ctl_multi.id)
        self.assertEqual(self.Line._canales_control(self.multi), 5)
        self.assertEqual(self.Line._canales_control(self.mono), 1)

    def test_motor_sin_control(self):
        codigos = self.codigos([self.motorizada()])
        self.assertIn('V_CONTROL_REQUERIDO', codigos)
        self.assertIn('V_CONTROL_PEDIDO', codigos)

    def test_monocanal_no_pide_canal(self):
        self.assertEqual(self.validar([self.motorizada(self.mono)]), [])

    def test_multicanal_pide_canal(self):
        self.assertIn('V_CANAL_REQUERIDO', self.codigos([self.motorizada(self.multi)]))
        self.assertEqual(self.validar([self.motorizada(self.multi, '1')]), [])

    def test_todas_sin_control(self):
        codigos = self.codigos([self.motorizada('0', '1')])
        self.assertIn('V_CONTROL_PEDIDO', codigos)
        self.assertIn('V_CANAL_SIN_CONTROL', codigos)

    def test_sin_interruptor_no_pide_control(self):
        self.assertEqual(self.validar([self.motorizada(interruptor_rf='sin')]), [])

    def test_canal_compartido(self):
        """«Sin control» usa un canal libre del multicanal de otra persiana."""
        duena = self.motorizada(self.multi, '1')
        self.assertEqual(self.validar([duena, self.motorizada('0', '2')]), [])
        self.assertIn('V_CANAL_TOMADO', self.codigos([duena, self.motorizada('0', '1')]))
        self.assertIn('V_CANAL_FUERA_RANGO', self.codigos([duena, self.motorizada('0', '9')]))

    def test_monocanal_no_presta_canales(self):
        codigos = self.codigos([self.motorizada(self.mono), self.motorizada('0', '1')])
        self.assertIn('V_CANAL_SIN_CONTROL', codigos)


@tagged('post_install', '-at_install', 'safra')
class TestRollos(SafraCommon):
    """Rollos = lotes (respuesta de Safra del 5-oct). La pieza es el alto
    más el aumento de tela del tubo (0,25 m en el R8 de prueba)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lotes = cls._color(cls.tela, 'ZTLOT', 'Blanco Lotes', ancho_rollo=2.5,
                               is_storable=True, tracking='lot')
        variante = cls.lotes.product_tmpl_id.product_variant_id
        bodega = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        Quant = cls.env['stock.quant']
        cls.rollo = {}
        for nombre, metros in (('ZT-R1', 2.0), ('ZT-R2', 5.0)):
            lote = cls.env['stock.lot'].create({
                'name': nombre, 'product_id': variante.id, 'company_id': cls.env.company.id})
            Quant._update_available_quantity(variante, bodega.lot_stock_id, metros, lot_id=lote)
            cls.rollo[nombre] = lote

    def con_lote(self, alto, **vals):
        return self.linea(color_id=self.lotes.id, height=alto, **vals)

    def test_reparto_al_rollo_que_mejor_ajusta(self):
        issues, sugeridos = self.Line._asignar_rollos([self.con_lote(1.8), self.con_lote(1.7)])
        self.assertEqual(issues, [])
        # 2,05 m solo cabe en el de 5 m; 1,95 m va al de 2 m (el más justo).
        self.assertEqual(sugeridos, {1: self.rollo['ZT-R2'], 2: self.rollo['ZT-R1']})

    def test_sin_rollo_suficiente_es_advertencia(self):
        lineas = [self.con_lote(1.8), self.con_lote(1.7), self.con_lote(3.0)]
        issues = self.mensajes(lineas, 'V_ROLLO_DISPONIBLE')
        self.assertEqual([(i['line'], i['severity']) for i in issues], [(1, 'warning')])

    def test_alineadas_de_un_mismo_rollo(self):
        lineas = [self.con_lote(2.6, aligned=True), self.con_lote(2.6, aligned=True)]
        issues = self.mensajes(lineas, 'V_ROLLO_ALINEADO')
        self.assertEqual([i['severity'] for i in issues], ['warning'])

    def test_sin_lotes_no_aplica(self):
        self.assertIsNone(self.blanco._rollos_disponibles())
