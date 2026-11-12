# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestValidacionesLinea(SafraCommon):
    """Reglas de cada persiana (safra.quote.line._validations), probadas
    por _validate_order como lo llama el portal."""

    def test_persiana_valida_sin_mensajes(self):
        self.assertEqual(self.validar([self.linea()]), [])

    def test_medidas_fuera_de_la_ficha(self):
        self.assertIn('V_RANGO_ANCHO', self.codigos([self.linea(width=0.2)]))
        self.assertIn('V_RANGO_ALTO', self.codigos([self.linea(height=4.5)]))

    def test_limites_del_producto_mandan(self):
        """Los U_AnchoMax/U_AltoMax del producto terminado mandan sobre la
        ficha del sistema."""
        self.assertNotIn('V_RANGO_ANCHO', self.codigos([self.linea(width=1.9)]))
        self.enrollable.product_tmpl_id.safra_u_ancho_max = 1.8
        self.assertIn('V_RANGO_ANCHO', self.codigos([self.linea(width=1.9)]))

    def test_ficha_de_exhibicion(self):
        self.enrollable.exh_width_max = 1.2
        self.assertNotIn('V_RANGO_ANCHO', self.codigos([self.linea(width=1.5)]))
        self.assertIn('V_RANGO_ANCHO', self.codigos([self.linea(width=1.5, exhibition=True)]))

    def test_fuera_de_la_tabla_de_estructura(self):
        self.enrollable.tech_width_max = 4.0
        self.assertIn('V_ESTRUCTURA', self.codigos([self.linea(width=3.5)]))

    def test_alto_maximo_y_requiere_motor(self):
        """Tela de 300 g/m² en 2 m de ancho: a mano el mecanismo soporta
        2.000 g (alto máximo 3,33 m); con motor, 10.000 g. Revisión cálculo
        de tubo (error 6): el error sale cuando ningún tubo manual alcanza."""
        (self.r16 | self.r24).write({'espacio_eje_techo': 60, 'diametro_tubo': 40,
                                     'carga_maxima': 2000})
        manual = self.linea(fabric_id=self.tela_pesada.id, color_id=self.pesada.id,
                            width=2.0, height=3.8)
        codigos = self.codigos([manual])
        self.assertIn('V_ALTO_MAXIMO', codigos)
        self.assertIn('V_REQUIERE_MOTOR', codigos)
        con_motor = dict(manual, has_motor=True, motor='M1', control='0',
                         control_channel='1')
        codigos = self.codigos([con_motor], cross=False)
        self.assertFalse(codigos & {'V_ALTO_MAXIMO', 'V_REQUIERE_MOTOR', 'V_PESO_MAXIMO'})

    def test_alto_mayor_a_tres_veces_el_ancho_es_advertencia(self):
        issues = self.mensajes([self.linea(width=0.5, height=1.8)], 'V_ALTO_3X_ANCHO')
        self.assertEqual([i['severity'] for i in issues], ['warning'])

    def test_ancho_minimo_con_motor(self):
        self.assertIn('V_ANCHO_MIN_MOTOR', self.codigos(
            [self.linea(width=0.6, height=1.0, has_motor=True, motor='M1')], cross=False))

    def test_localizacion_obligatoria(self):
        issues = self.mensajes([self.linea(location=False)], 'V_LOCALIZACION')
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0]['message'].startswith('E13095'))

    def test_ancho_mayor_al_rollo(self):
        """Tela no atravesable con rollo de 2,50 m (E20007)."""
        self.assertIn('V_ANCHO_ROLLO', self.codigos([self.linea(width=2.8)]))
        self.assertNotIn('V_ANCHO_ROLLO', self.codigos([self.linea(width=2.4)]))

    def test_corte_atravesado_requiere_aceptacion(self):
        """Tela atravesable más ancha que el rollo: se corta atravesada y el
        cliente debe aceptarlo (E20017)."""
        self.pesada.product_tmpl_id.safra_u_ancho = 2.5
        linea = self.linea(fabric_id=self.tela_pesada.id, color_id=self.pesada.id,
                           width=2.8, height=1.0)
        self.assertIn('V_CORTE_ATRAVESADO', self.codigos([linea], cross=False))
        self.assertNotIn('V_CORTE_ATRAVESADO', self.codigos(
            [dict(linea, acepta_atravesado=True)], cross=False))

    def test_cadena_extra_en_rango(self):
        self.assertIn('V_CADENA_EXTRA', self.codigos([self.linea(extra_chain=10)]))
        self.assertNotIn('V_CADENA_EXTRA', self.codigos([self.linea(extra_chain=2.0)]))

    def test_diseno_de_impresion_sin_diseno(self):
        self.assertIn('V_DISENO_SELECCION', self.codigos([self.linea(design_print=True)]))
        self.assertNotIn('V_DISENO_SELECCION', self.codigos(
            [self.linea(design_print=True, custom_design='DSPRUEBA')]))

    def test_telas_repetidas(self):
        repetida = self.linea(fabric_id_2=self.tela.id, color_id_2=self.blanco.id)
        self.assertIn('V_TELAS_REPETIDAS', self.codigos([repetida]))
        otro_color = self.linea(fabric_id_2=self.tela.id, color_id_2=self.gris.id)
        self.assertNotIn('V_TELAS_REPETIDAS', self.codigos([otro_color]))

    def test_cenefa_entera(self):
        # Reunión 20-oct: la cenefa entera solo se frena cuando el ancho
        # supera el rollo (2,50 m); reunión 28-oct: y la tela no es atravesable.
        tela = {'cenefa_panel': '2', 'corte_cenefa': '2'}
        dentro = self.linea(attribute_values=tela)
        self.assertNotIn('V_CENEFA_ENTERA', self.codigos([dentro]))
        linea = self.linea(width=2.8, attribute_values=tela)
        self.assertIn('V_CENEFA_ENTERA', self.codigos([linea]))
        self.tela.pierceable_type = 'si'
        self.assertNotIn('V_CENEFA_ENTERA', self.codigos([linea]))

    def test_dos_en_uno(self):
        sistema = self.env.ref('website_quotes_safra.system_32', raise_if_not_found=False)
        if not sistema:
            self.skipTest('La base no tiene el sistema ENROLLABLE 2 EN 1')
        linea = self.linea(system_id=sistema.id)
        self.assertIn('V_SEGUNDA_TELA', self.codigos([linea], cross=False))
        # Dos telas que no son una Blackout y una Sheer.
        linea = self.linea(system_id=sistema.id, fabric_id_2=self.tela.id,
                           color_id_2=self.gris.id)
        self.assertIn('V_2EN1_FAMILIA', self.codigos([linea], cross=False))


@tagged('post_install', '-at_install', 'safra')
class TestValidacionesPanel(SafraCommon):
    """Reglas de Panel Track en la línea (combinación, apertura y riel)."""

    def test_sin_combinacion_para_los_telos(self):
        self.assertIn('V_PANEL_LAMAS', self.codigos([self.linea_panel(3)]))

    def test_apertura_fuera_de_las_combinaciones(self):
        """Con 4 telos no hay Extremos (necesita 3 canales)."""
        self.assertIn('V_PANEL_APERTURA', self.codigos([self.linea_panel(4, 'extremos')]))
        self.assertNotIn('V_PANEL_APERTURA', self.codigos([self.linea_panel(4, 'centro')]))
        # Panel Japonés usa códigos numéricos: 3 = Extremos.
        self.assertIn('V_PANEL_APERTURA', self.codigos([self.linea_panel(4, '3')]))

    def test_tipo_de_riel_de_la_combinacion(self):
        """Reunión 09-oct: el Tipo de Riel debe ser el de la combinación."""
        self.assertNotIn('V_PANEL_RIEL', self.codigos([self.linea_panel(4, 'derecha', 'r4')]))
        self.assertIn('V_PANEL_RIEL', self.codigos([self.linea_panel(4, 'derecha', 'r5')]))
        # 7 telos van con Riel Velcrado, no con el de 6 vías.
        self.assertIn('V_PANEL_RIEL', self.codigos([self.linea_panel(7, 'derecha', 'r6')]))
        self.assertNotIn('V_PANEL_RIEL', self.codigos([self.linea_panel(7, 'derecha', 'rv')]))
        # «Auto» no se restringe.
        self.assertNotIn('V_PANEL_RIEL', self.codigos([self.linea_panel(7, 'derecha', 'auto')]))

    def test_riel_con_apertura_libre(self):
        """Mejoras Sprint 1.1 (21-oct, fila 16): con Apertura Libre el riel es
        uno de los de las combinaciones posibles para esos telos."""
        self.assertNotIn('V_PANEL_RIEL', self.codigos([self.linea_panel(4, 'libre', 'r4')]))
        issues = self.mensajes([self.linea_panel(4, 'libre', 'r6')], 'V_PANEL_RIEL')
        self.assertEqual(len(issues), 1)
        self.assertIn('apertura libre', issues[0]['message'])
        self.assertNotIn('V_PANEL_RIEL', self.codigos([self.linea_panel(4, 'libre', 'auto')]))

    def test_lamas_por_tela(self):
        """Con dos telas la suma de lamas por tela debe dar el total."""
        def con(l1, l2):
            return self.linea_panel(7, 'derecha', fabric_id_2=self.tela.id,
                                    color_id_2=self.gris.id,
                                    attribute_values={'lamas_tela_1': l1, 'lamas_tela_2': l2})
        self.assertFalse(self.codigos([con(4, 3)]) & {'V_LAMAS_TELA', 'V_LAMAS_TELA_SUMA'})
        self.assertIn('V_LAMAS_TELA_SUMA', self.codigos([con(3, 3)]))
        self.assertIn('V_LAMAS_TELA', self.codigos([con(5, 3)]))


@tagged('post_install', '-at_install', 'safra')
class TestReglasConfigurables(SafraCommon):
    """Lo que el funcional cambia en Configuración → Validaciones."""

    def regla(self, code):
        Rule = self.env['safra.validation.rule'].with_context(active_test=False)
        return Rule.search([('code', '=', code)], limit=1) or Rule.create(
            {'code': code, 'name': code})

    def test_regla_apagada_no_corre(self):
        self.regla('V_LOCALIZACION').active = False
        self.assertNotIn('V_LOCALIZACION', self.codigos([self.linea(location=False)]))

    def test_mensaje_y_severidad_configurados(self):
        self.regla('V_LOCALIZACION').write({'condition_code': False, 'severity': 'warning',
                                            'message': 'Falta el espacio'})
        issues = self.mensajes([self.linea(location=False)], 'V_LOCALIZACION')
        self.assertEqual([(i['severity'], i['message']) for i in issues],
                         [('warning', 'Falta el espacio')])

    def test_regla_nueva_por_condicion(self):
        self.env['safra.validation.rule'].create({
            'code': 'V_PRUEBA', 'name': 'Prueba', 'severity': 'error',
            'condition_code': 'ancho > 2 and not con_motor',
            'message': 'Más de 2 m ({ancho} m) va con motor'})
        self.assertNotIn('V_PRUEBA', self.codigos([self.linea(width=1.5)]))
        issues = self.mensajes([self.linea(width=2.4)], 'V_PRUEBA')
        self.assertEqual([i['message'] for i in issues], ['Más de 2 m (2.4 m) va con motor'])

    def test_condicion_con_error_no_rompe(self):
        # Sprint 1.7: la mal escrita ya no se deja guardar; la que falla con
        # los datos reales se ignora y queda en el log.
        with self.assertRaises(ValidationError):
            self.env['safra.validation.rule'].create({
                'code': 'V_ROTA', 'name': 'Rota', 'condition_code': 'ancho >'})
        self.env['safra.validation.rule'].create({
            'code': 'V_ROTA', 'name': 'Rota', 'condition_code': 'ancho / 0 > 1'})
        with self.assertLogs('odoo.addons.website_quotes_safra.models.safra_quote', 'WARNING'):
            self.assertEqual(self.validar([self.linea()]), [])
