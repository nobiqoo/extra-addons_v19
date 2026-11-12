# -*- coding: utf-8 -*-
import textwrap

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

from .common import SafraCommon

RESPUESTA = textwrap.dedent('''\
    Claro, aquí está:

    **CONDICIÓN:**
    ```python
    result = apertura == '4' and (total_lamas < 4 or total_lamas % 2 != 0)
    ```

    **MENSAJE:**
    «E13095: Con apertura Centro los telos deben ser pares y mínimo 4 (tiene {total_lamas}).»

    PRUEBAS:
    - Debe salir con: apertura Centro y 3 telos
    - No debe salir con: apertura Centro y 4 telos

    AVISOS:
    Ninguno
''')


@tagged('post_install', '-at_install', 'safra')
class TestPromptIA(SafraCommon):
    """Revisión 27-oct: instrucción para escribir la condición de una
    validación con una IA externa y paso de su respuesta a la validación."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.regla = cls.env['safra.validation.rule'].create({
            'code': 'R_PRUEBA_IA', 'name': 'Prueba IA', 'momento': 'linea',
            'severity': 'error'})
        cls.mapeo_apertura = cls.env['safra.system.field'].search([
            ('system_id', '=', cls.panel.id), ('field_id', '=', cls._campo('apertura').id)])
        cls.env['safra.system.field.option'].create([
            {'system_field_id': cls.mapeo_apertura.id, 'value': '3', 'name': 'Extremos'},
            {'system_field_id': cls.mapeo_apertura.id, 'value': '4', 'name': 'Centro'},
        ])

    def asistente(self, sistemas=None, **vals):
        return self.env['safra.validation.rule.prompt'].create(dict({
            'rule_id': self.regla.id,
            'system_ids': [(6, 0, (self.panel if sistemas is None else sistemas).ids)],
        }, **vals))

    def test_instruccion_con_los_datos_del_sistema(self):
        prompt = self.asistente(solicitud='Con apertura Centro, telos pares y mínimo 4.').prompt
        self.assertIn("PRUEBA PANEL (código 'ZT11')", prompt)
        self.assertIn('NO filtres por sistema', prompt)
        self.assertIn("«sistema» es el CÓDIGO ('ZT11')", prompt)
        self.assertIn("apertura: Tipo de Apertura — texto, uno de: '3' Extremos, '4' Centro", prompt)
        self.assertIn('== CAMPOS DE PRUEBA PANEL ==', prompt)
        self.assertTrue(prompt.endswith('Con apertura Centro, telos pares y mínimo 4.'))

    def test_sin_cotizaciones_usa_una_persiana_vacia(self):
        prompt = self.asistente().prompt
        self.assertIn('VARIABLES (con el valor de una persiana vacía)', prompt)
        self.assertIn("sistema = 'ZT11'", prompt)

    def test_campo_con_codigo_de_variable_propia(self):
        """ancho_telo es variable del motor y código de campo: en la
        condición manda la variable, así que no se lista como campo."""
        self.env['safra.system.field'].create({
            'system_id': self.panel.id, 'field_id': self._campo('ancho_telo').id, 'sequence': 500})
        codigos = [c['code'] for c in self.asistente()._campos_prompt(self.panel)]
        self.assertIn('apertura', codigos)
        self.assertNotIn('ancho_telo', codigos)

    def test_todos_los_sistemas(self):
        prompt = self.asistente(sistemas=self.env['safra.system']).prompt
        self.assertIn('- Sistemas: todos.', prompt)
        self.assertIn("filtra con sistema in (...)", prompt)
        self.assertIn("'ZT11': PRUEBA PANEL", prompt)

    def test_incluye_la_condicion_actual(self):
        self.regla.write({'condition_code': 'hallazgo', 'message': 'Mensaje viejo'})
        prompt = self.asistente().prompt
        self.assertIn('Ya tiene esta condición', prompt)
        self.assertIn('- Mensaje actual: Mensaje viejo', prompt)
        self.assertIn('«hallazgo» es lo que encontró el cálculo interno', prompt)

    def test_pasar_la_respuesta_a_la_validacion(self):
        self.asistente(respuesta=RESPUESTA).action_aplicar()
        self.assertEqual(self.regla.condition_code,
                         "result = apertura == '4' and (total_lamas < 4 or total_lamas % 2 != 0)")
        self.assertEqual(self.regla.message,
                         'E13095: Con apertura Centro los telos deben ser pares y mínimo 4 '
                         '(tiene {total_lamas}).')
        self.assertEqual(self.regla.system_ids, self.panel)
        tres = self.mensajes([self.linea_panel(3, apertura='4')], 'R_PRUEBA_IA', cross=False)
        self.assertEqual([m['message'] for m in tres],
                         ['E13095: Con apertura Centro los telos deben ser pares y mínimo 4 '
                          '(tiene 3).'])
        self.assertFalse(self.mensajes([self.linea_panel(4, apertura='4')], 'R_PRUEBA_IA',
                                       cross=False))

    def test_valores_de_la_estructura(self):
        """Revisión 28-oct: la instrucción y la pestaña «Valores que puede
        usar» traen los nombres exactos de los tubos (la IA había escrito
        'TUBO_40' por «tubo de 40»)."""
        wiz = self.asistente(sistemas=self.enrollable)
        self.assertIn("estructura['tubo'] es uno de: 'R8', 'R16', 'R24'", wiz.prompt)
        self.assertIn("estructura['mecanismo'] es uno de:", wiz.prompt)
        self.assertIn('<code>R16</code>', wiz.valores_html)
        self.assertIn('Estructura por Ancho', wiz.valores_html)
        # Sistema sin estructura: no sale la sección.
        self.assertNotIn('VALORES DE LA ESTRUCTURA', self.asistente().prompt)

    def test_valores_de_los_campos(self):
        html = self.asistente().valores_html
        self.assertIn('<code>apertura</code>', html)
        self.assertIn('<code>4</code> = Centro', html)
        # Explica cómo va la variable (sin comillas) y el valor (con comillas).
        self.assertIn('<b>Variable:</b> sin comillas', html)
        self.assertIn("<code>apertura == '4'</code>", str(html))

    def test_valores_de_los_controles(self):
        """Los controles salen con el valor que guarda el portal: «Sin
        control» es '0' (no el código ni el id de su línea) y los demás
        'ref-<línea>'."""
        opciones = dict(self.asistente()._opciones_referencia(
            self.ctl_sin.fabric_id.category_id, self.enrollable))
        self.assertEqual(opciones['0'], 'Sin control')
        self.assertIn('ref-%d' % self.ctl_multi.id, opciones)
        self.assertNotIn('ZT-SIN', opciones)

    def test_reglas_para_copiar_valores_exactos(self):
        prompt = self.asistente().prompt
        self.assertIn('se copian EXACTAMENTE como están en las listas', prompt)
        self.assertIn("l['atributos'].get('same_header')", prompt)
        # Revisión 28-oct: cómo leer códigos y nombres de pantalla en la solicitud.
        self.assertIn('== CÓMO LEER LO QUE PIDE EL USUARIO ==', prompt)
        self.assertIn("Nunca same_header == 'True'", prompt)
        self.assertLess(prompt.index('CÓMO LEER LO QUE PIDE'), prompt.index('LO QUE QUIERO VALIDAR'))

    def test_atributos_con_todos_los_campos(self):
        """Revisión 28-oct: en otras_lineas, l['atributos'] trae también los
        campos de columna (Mismo cabezal), como dice la instrucción."""
        self.regla.write({
            'momento': 'pedido', 'message': 'En secuencia',
            'condition_code': ("grupo = [l for l in otras_lineas if l['atributos'].get('same_header') "
                               "and l['secuencia'] == sequence_name]\nresult = same_header and len(grupo) > 0")})
        lineas = [self.linea(same_header=True, sequence_name='S1', soporte_izq='MANDO', soporte_der='DEP'),
                  self.linea(same_header=True, sequence_name='S1', soporte_izq='DEP', soporte_der='TERMINAL')]
        self.assertTrue(self.mensajes(lineas, 'R_PRUEBA_IA'))
        self.assertFalse(self.mensajes([self.linea(), self.linea()], 'R_PRUEBA_IA'))

    def test_variable_con_varios_registros(self):
        # Un motor con un kit por tubo: motor_kits trae varios kits y el asistente no se cae.
        Prompt = self.env['safra.validation.rule.prompt']
        varios = self.enrollable | self.panel
        self.assertEqual(Prompt._texto_valor(varios), repr(varios.mapped('display_name')))
        self.assertEqual(Prompt._texto_valor(self.panel), repr(self.panel.display_name))
        self.assertEqual(Prompt._texto_valor(self.env['safra.system']), 'vacío')
        kit = self.env['safra.motor.kit'].search([], limit=2)
        if len(kit) == 2:
            linea = self.env['safra.quote.line'].search([], order='id desc', limit=1)
            ctx = {'motor_kits': kit}
            texto = self.asistente()._seccion_variables(ctx, linea)
            self.assertIn(repr(kit.mapped('display_name')), texto)

    def test_solicitud_guardada_para_la_proxima_vez(self):
        """Revisión 28-oct: lo escrito en «¿Qué quiere validar?» queda en la
        validación al cerrar o al pasar la respuesta, y sale escrito al
        abrir otra vez el asistente."""
        texto = 'Con apertura Centro, telos pares y mínimo 4.'
        self.asistente(solicitud=texto).action_cerrar()
        self.assertEqual(self.regla.solicitud_ia, texto)
        accion = self.regla.action_prompt_ia()
        nuevo = self.env['safra.validation.rule.prompt'].with_context(accion['context']).create(
            {'rule_id': self.regla.id})
        self.assertEqual(nuevo.solicitud, texto)
        self.assertIn(texto, nuevo.prompt)
        otro = 'Con apertura Extremos, mínimo 6 telos.'
        self.asistente(solicitud=otro, respuesta=RESPUESTA).action_aplicar()
        self.assertEqual(self.regla.solicitud_ia, otro)

    def test_respuesta_en_una_linea(self):
        self.asistente(respuesta='CONDICIÓN: ancho > 3\nMensaje sugerido: "Muy ancha."').action_aplicar()
        self.assertEqual(self.regla.condition_code, 'ancho > 3')
        self.assertEqual(self.regla.message, 'Muy ancha.')

    def test_respuesta_sin_condicion(self):
        with self.assertRaisesRegex(UserError, 'No encontré la parte «CONDICIÓN:»'):
            self.asistente(respuesta='ancho > 3').action_aplicar()

    def test_condicion_con_error_se_devuelve_a_la_ia(self):
        with self.assertRaisesRegex(UserError, 'Copie este mensaje en la IA'):
            self.asistente(respuesta='CONDICIÓN:\nancho_inventado > 3\nMENSAJE: x').action_aplicar()


@tagged('post_install', '-at_install', 'safra')
class TestCatalogoAparte(TransactionCase):
    """Revisión 27-oct: el catálogo del archivo de Safra en su propio menú y
    las reglas que el archivo marca activas, encendidas."""

    def test_menus_separados(self):
        Rule = self.env['safra.validation.rule'].with_context(active_test=False)
        reglas = self.env.ref('website_quotes_safra.action_safra_validation_rule')
        catalogo = self.env.ref('website_quotes_safra.action_safra_validation_catalogo')
        en_reglas = Rule.search(safe_eval(reglas.domain))
        en_catalogo = Rule.search(safe_eval(catalogo.domain))
        self.assertIn('V_TELAS_REPETIDAS', en_reglas.mapped('code'))
        self.assertIn('E13095-65', en_catalogo.mapped('code'))
        self.assertFalse(en_reglas & en_catalogo)
        self.assertEqual(set(en_catalogo.mapped('estado')) & {'portal'}, set())

    def test_activar_segun_archivo_una_sola_vez(self):
        Rule = self.env['safra.validation.rule'].with_context(active_test=False)
        regla = Rule.search([('code', '=', 'V_TELAS_REPETIDAS')])
        ficha = Rule.search([('code', '=', 'E13095-65')])
        _ficha, vieja, nueva = Rule.ACTIVAR_SEGUN_ARCHIVO['V_TELAS_REPETIDAS']
        regla.active = False
        ficha.write({'estado': 'pendiente_safra', 'description': 'Nota.\n' + vieja})
        # Una función del catálogo marcada «Activa en el portal» sin condición.
        suelta = Rule.search([('code', '=', 'E10027')])
        suelta.write({'estado': 'portal', 'active': True, 'condition_code': False})
        self.env['ir.config_parameter'].sudo().set_param(
            'website_quotes_safra.activar_segun_archivo_27oct', False)
        Rule._activar_segun_archivo_safra()
        self.assertTrue(regla.active)
        self.assertEqual(ficha.estado, 'cubierta')
        self.assertEqual(ficha.description, 'Nota.\n' + nueva)
        self.assertEqual((suelta.estado, suelta.active), ('pendiente_safra', False))
        # Si el funcional la vuelve a apagar, la actualización no la toca.
        regla.active = False
        Rule._activar_segun_archivo_safra()
        self.assertFalse(regla.active)

    def test_codigo_repetido_dice_donde_esta(self):
        Rule = self.env['safra.validation.rule']
        with self.assertRaisesRegex(ValidationError, 'ya lo tiene «ValidaTipoPlanoImplementacion» '
                                    r'\(en el menú Catálogo archivo Safra, inactiva\)'):
            Rule.create({'code': 'E13095', 'name': 'Estampado en pausa'})
        regla = Rule.create({'code': 'R_PRUEBA_CODIGO', 'name': 'Prueba'})
        with self.assertRaisesRegex(ValidationError, 'en Validaciones'):
            regla.code = 'V_TELAS_REPETIDAS'
        regla.code = 'R_PRUEBA_CODIGO'
