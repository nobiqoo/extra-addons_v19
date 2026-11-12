# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestCodigoEnMensaje(SafraCommon):
    """Revisión 28-oct: el mensaje que ve la persona termina con el código
    de la regla para buscarla en Validaciones."""

    def test_mensaje_con_codigo(self):
        issues = self.Line._validate_order([self.linea(location='')], cross=False)
        loc = [i for i in issues if i['code'] == 'V_LOCALIZACION']
        self.assertTrue(loc)
        self.assertTrue(loc[0]['message'].endswith(' [V_LOCALIZACION]'), loc[0]['message'])

    def test_mensaje_editado_en_validaciones(self):
        regla = self.env['safra.validation.rule'].search([('code', '=', 'V_LOCALIZACION')])
        regla.message = 'Escriba la localización.'
        issues = self.Line._validate_order([self.linea(location='')], cross=False)
        self.assertIn('Escriba la localización. [V_LOCALIZACION]', [i['message'] for i in issues])

    def test_codigo_sin_regla_no_se_agrega(self):
        issues = self.Line._con_codigo_regla([{'line': 1, 'code': 'X_SIN_REGLA', 'message': 'Hola'}])
        self.assertEqual(issues[0]['message'], 'Hola')

    def test_no_se_repite(self):
        issues = [{'line': 1, 'code': 'V_LOCALIZACION', 'message': 'Hola [V_LOCALIZACION]'}]
        self.assertEqual(self.Line._con_codigo_regla(issues)[0]['message'], 'Hola [V_LOCALIZACION]')


@tagged('post_install', '-at_install', 'safra')
class TestClaveInterna(SafraCommon):
    """Revisión 28-oct: Safra cambia el Código de las reglas; el programa
    las sigue encontrando por su clave interna."""

    def setUp(self):
        super().setUp()
        self.Rule = self.env['safra.validation.rule']

    def renombrar(self, clave, nuevo):
        regla = self.Rule._por_clave([clave])
        self.assertEqual(len(regla), 1, clave)
        regla.code = nuevo
        return regla

    def test_reglas_con_clave(self):
        sin = self.Rule.with_context(active_test=False).search(
            [('code', '=like', 'V\\_%'), ('clave', '=', False)])
        self.assertFalse(sin.mapped('code'))

    def test_regla_del_calculo_renombrada(self):
        """Regla que calcula el programa (condición «hallazgo»): con otro
        Código sigue saltando, con su mensaje y el Código nuevo al final, y
        se apaga desde Validaciones."""
        self.enrollable.tech_width_max = 4.0
        regla = self.renombrar('V_ESTRUCTURA', 'SAFRA_ESTRUCTURA')
        regla.write({'message': 'Fuera de la tabla.', 'severity': 'warning'})
        issues = self.Line._validate_order([self.linea(width=3.5)], cross=False)
        est = [i for i in issues if i['code'] == 'V_ESTRUCTURA']
        self.assertEqual([(i['message'], i['severity']) for i in est],
                         [('Fuera de la tabla. [SAFRA_ESTRUCTURA]', 'warning')])
        regla.active = False
        issues = self.Line._validate_order([self.linea(width=3.5)], cross=False)
        self.assertFalse([i for i in issues if i['code'] == 'V_ESTRUCTURA'])

    def test_regla_con_condicion_renombrada(self):
        regla = self.renombrar('V_RANGO_ANCHO', 'E_ANCHO_SISTEMA')
        issues = self.Line._validate_order([self.linea(width=3.5)], cross=False)
        rango = [i for i in issues if i['code'] == 'V_RANGO_ANCHO']
        self.assertTrue(rango and rango[0]['message'].endswith(' [E_ANCHO_SISTEMA]'), rango)
        self.assertEqual(regla.clave, 'V_RANGO_ANCHO')

    def test_ajustes_y_portal_por_clave(self):
        """Lo que el programa consulta por su clave (p. ej. el interruptor de
        estampación de Ajustes) sigue funcionando con otro Código."""
        regla = self.renombrar('V_ESTAMPADO_FUERA_SERVICIO', 'E_ESTAMPADO_OFF')
        self.assertEqual(self.Rule.get_config('V_ESTAMPADO_FUERA_SERVICIO')['severity'], regla.severity)
        ajustes = self.env['res.config.settings'].create({'safra_estampado_fuera_servicio': True})
        ajustes.set_values()
        self.assertTrue(regla.active)

    def test_regla_nueva_sin_clave(self):
        nueva = self.Rule.create({'code': 'R_PRUEBA_CLAVE', 'name': 'Prueba', 'momento': 'linea',
                                  'condition_code': 'ancho > 9', 'message': 'Muy ancha'})
        self.assertFalse(nueva.clave)
        self.assertEqual(nueva._clave_programa(), 'R_PRUEBA_CLAVE')


@tagged('post_install', '-at_install', 'safra')
class TestMomentoSecuencia(SafraCommon):
    """Revisión 28-oct: momento «Al aplicar la secuencia» de Validaciones."""

    def setUp(self):
        super().setUp()
        self.regla = self.env['safra.validation.rule'].create({
            'code': 'R_SEC_MAX2', 'name': 'Máximo 2 persianas por secuencia', 'severity': 'error',
            'momento': 'secuencia', 'condition_code': 'len(secuencia_lineas) > 2',
            'message': 'Máximo 2 persianas por secuencia.'})

    def secuencia(self, n):
        sops = [('MANDO', 'DEP')] + [('DEP', 'DEP')] * (n - 2) + [('DEP', 'TERMINAL')]
        return [self.linea(same_header=True, sequence_name='S1', soporte_izq=a, soporte_der=b)
                for a, b in sops]

    def codigos_en(self, lineas, **kw):
        return {i['code'] for i in self.Line._validate_order(lineas, **kw)}

    def test_se_revisa_al_aplicar_y_al_finalizar(self):
        tres = self.secuencia(3)
        self.assertIn('R_SEC_MAX2', self.codigos_en(tres, cross=True, momento='secuencia'))
        self.assertIn('R_SEC_MAX2', self.codigos_en(tres, cross=True))
        self.assertNotIn('R_SEC_MAX2', self.codigos_en(tres, cross=False))
        self.assertNotIn('R_SEC_MAX2', self.codigos_en(self.secuencia(2), cross=True, momento='secuencia'))

    def test_en_el_configurador_solo_las_de_ese_momento(self):
        """Al aplicar no salen las reglas de otros momentos ni los cálculos
        del programa (p. ej. la secuencia incompleta)."""
        lineas = self.secuencia(2)
        lineas[1]['soporte_der'] = False
        lineas[0]['location'] = ''
        codigos = self.codigos_en(lineas, cross=True, momento='secuencia')
        self.assertFalse(codigos & {'V_SECUENCIA_PENDIENTE', 'V_LOCALIZACION'}, codigos)

    def test_un_solo_mensaje_por_secuencia(self):
        issues = [i for i in self.Line._validate_order(self.secuencia(3), cross=True, momento='secuencia')
                  if i['code'] == 'R_SEC_MAX2']
        self.assertEqual(len(issues), 1)

    def test_secuencia_lineas_y_soportes(self):
        self.regla.condition_code = ("'MOTOR' in (linea.soporte_izq, linea.soporte_der) and "
                                     "len([l for l in secuencia_lineas if 'DEP' in "
                                     "(l['linea'].soporte_izq, l['linea'].soporte_der)]) >= 2")
        lineas = self.secuencia(2)
        lineas[0]['soporte_izq'] = 'MOTOR'
        self.assertIn('R_SEC_MAX2', self.codigos_en(lineas, cross=True, momento='secuencia'))
        lineas[0]['soporte_izq'] = 'MANDO'
        self.assertNotIn('R_SEC_MAX2', self.codigos_en(lineas, cross=True, momento='secuencia'))
