# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestReglasParametrizables(SafraCommon):
    """Sprint 1.7 (video del 23-oct): toda validación se dispara por su
    Condición (código), en un solo momento y en los sistemas que se elijan."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env['safra.validation.rule'].sudo()

    def regla(self, **vals):
        return self.Rule.create(dict({'code': 'R_PRUEBA', 'name': 'Prueba', 'severity': 'error',
                                      'condition_code': 'ancho > 2'}, **vals))

    def validar_campo(self, lineas, campo):
        return self.Line._validate_order(lineas, cross=False, campo=campo)

    # --- Momento de disparo -------------------------------------------

    def test_momento_linea(self):
        self.regla(message='Más de 2 m')
        self.assertIn('R_PRUEBA', self.codigos([self.linea(width=2.4)], cross=False))
        self.assertIn('R_PRUEBA', self.codigos([self.linea(width=2.4)]))
        # Al digitar un campo solo salen las reglas de ese campo.
        self.assertFalse(self.validar_campo([self.linea(width=2.4)], 'width'))

    def test_momento_pedido_solo_al_finalizar(self):
        self.regla(momento='pedido')
        self.assertNotIn('R_PRUEBA', self.codigos([self.linea(width=2.4)], cross=False))
        self.assertIn('R_PRUEBA', self.codigos([self.linea(width=2.4)]))

    def test_momento_campo(self):
        self.regla(momento='campo', trigger_field_id=self._campo('width').id,
                   message='Con {ancho} m va motorizada', severity='warning')
        issues = self.validar_campo([self.linea(width=2.4)], 'width')
        self.assertEqual([(i['code'], i['severity'], i['message']) for i in issues],
                         [('R_PRUEBA', 'warning', 'Con 2.4 m va motorizada [R_PRUEBA]')])
        self.assertFalse(self.validar_campo([self.linea(width=2.4)], 'height'))
        self.assertFalse(self.validar_campo([self.linea(width=1.5)], 'width'))
        # También se revisa al guardar la línea y al finalizar.
        self.assertIn('R_PRUEBA', self.codigos([self.linea(width=2.4)], cross=False))
        self.assertIn('R_PRUEBA', self.codigos([self.linea(width=2.4)]))

    def test_momento_campo_exige_el_campo(self):
        with self.assertRaises(ValidationError):
            self.regla(momento='campo')

    def test_campos_que_disparan_por_sistema(self):
        self.regla(momento='campo', trigger_field_id=self._campo('width').id,
                   system_ids=[(6, 0, self.panel.ids)])
        self.assertIn('width', self.Rule._campos_disparo(self.panel))
        self.assertNotIn('width', self.Rule._campos_disparo(self.enrollable))

    # --- Sistemas, severidad, mensaje ---------------------------------

    def test_sistemas(self):
        self.regla(system_ids=[(6, 0, self.panel.ids)])
        self.assertNotIn('R_PRUEBA', self.codigos([self.linea(width=2.4)]))
        self.assertIn('R_PRUEBA', self.codigos([self.linea_panel(4, ancho=2.4)], cross=False))

    def test_condicion_de_varias_lineas_y_mensaje(self):
        self.regla(severity='info',
                   condition_code='area = ancho * alto\nresult = area > 4 and not con_motor',
                   message='El área ({area:.2f} m²) es grande para manual')
        issues = self.mensajes([self.linea(width=2.5, height=2.0)], 'R_PRUEBA')
        self.assertEqual([(i['severity'], i['message']) for i in issues],
                         [('info', 'El área (5.00 m²) es grande para manual')])
        self.assertFalse(self.mensajes([self.linea(width=1.5, height=1.8)], 'R_PRUEBA'))

    def test_campos_del_formulario_como_variables(self):
        self.regla(condition_code="quantity == 3 and location == 'Sala' and not aligned",
                   message='Línea {numero}')
        self.assertEqual([i['message'] for i in self.mensajes(
            [self.linea(), self.linea(quantity=3)], 'R_PRUEBA')], ['Línea 2'])

    def test_comparar_lineas_del_pedido(self):
        self.regla(momento='pedido', message='En {localizacion} hay más de 2 alineadas',
                   condition_code="alineado and len([l for l in lineas if l['alineado'] "
                                  "and l['localizacion'] == localizacion]) > 2")
        tres = [self.linea(aligned=True) for _i in range(3)]
        issues = self.mensajes(tres, 'R_PRUEBA')
        # Mismo mensaje en todas las líneas: sale una vez, para el pedido.
        self.assertEqual([(i['line'], i['message']) for i in issues],
                         [(0, 'En Sala hay más de 2 alineadas')])
        self.assertFalse(self.mensajes(tres[:2], 'R_PRUEBA'))

    def test_pedido_completo(self):
        self.regla(momento='pedido', condition_code="pedido['unidades'] > 4",
                   message='{pedido[unidades]} unidades')
        issues = self.mensajes([self.linea(quantity=3), self.linea(quantity=2)], 'R_PRUEBA')
        self.assertEqual([(i['line'], i['message']) for i in issues], [(0, '5 unidades')])

    # --- Hallazgo del cálculo interno -----------------------------------

    def test_hallazgo(self):
        regla = self.Rule.search([('code', '=', 'V_EXPRESS_CANTIDAD')])
        regla.condition_code = 'hallazgo'
        once = [self.linea(quantity=11)]
        issues = self.Line._validate_order(once, pedido={'safra_express': True})
        self.assertEqual([i['line'] for i in issues if i['code'] == 'V_EXPRESS_CANTIDAD'], [0])
        # El funcional le agrega una condición y usa los datos del hallazgo.
        regla.write({'condition_code': "hallazgo and hallazgo['total'] > 12",
                     'message': 'Express hasta {tope}: {total}'})
        issues = self.Line._validate_order(once, pedido={'safra_express': True})
        self.assertNotIn('V_EXPRESS_CANTIDAD', {i['code'] for i in issues})
        issues = self.Line._validate_order([self.linea(quantity=13)], pedido={'safra_express': True})
        self.assertEqual([i['message'] for i in issues if i['code'] == 'V_EXPRESS_CANTIDAD'],
                         ['Express hasta 10: 13 [V_EXPRESS_CANTIDAD]'])
        # Sin condición vuelve el cálculo interno.
        regla.condition_code = False
        issues = self.Line._validate_order(once, pedido={'safra_express': True})
        self.assertIn('V_EXPRESS_CANTIDAD', {i['code'] for i in issues})

    def test_regla_interna_por_sistema_y_momento(self):
        regla = self.Rule.search([('code', '=', 'V_LOCALIZACION')])
        sin_loc = [self.linea(location=False)]
        regla.system_ids = [(6, 0, self.panel.ids)]
        self.assertNotIn('V_LOCALIZACION', self.codigos(sin_loc))
        regla.write({'system_ids': [(5, 0, 0)], 'momento': 'pedido'})
        self.assertNotIn('V_LOCALIZACION', self.codigos(sin_loc, cross=False))
        self.assertIn('V_LOCALIZACION', self.codigos(sin_loc))

    def test_inactiva(self):
        self.regla(active=False)
        self.assertNotIn('R_PRUEBA', self.codigos([self.linea(width=2.4)]))

    # --- Revisión al guardar y «Probar» ----------------------------------

    def test_revision_al_guardar(self):
        casos = {
            'anchoo > 2': 'No existe la variable «anchoo»',
            'ancho > (2': 'Error de escritura',
            'x = ancho * 2\nx > 3': 'debe terminar asignando «result»',
        }
        for condicion, texto in casos.items():
            with self.assertRaises(ValidationError) as error:
                self.regla(code='R_%d' % len(condicion), condition_code=condicion)
            self.assertIn(texto, str(error.exception))
        with self.assertRaises(ValidationError) as error:
            self.regla(message='Ancho {anchura}')
        self.assertIn('{anchura}', str(error.exception))
        # Los comodines del cálculo interno solo se conocen con «hallazgo».
        self.regla(code='R_OK', condition_code='hallazgo', message='{alto_maximo}')

    def test_probar_regla(self):
        regla = self.regla(system_ids=[(6, 0, self.enrollable.ids)], message='Ancho {ancho}')
        filas = self.Line._probar_regla(regla, [self.linea(width=2.4), self.linea(),
                                                self.linea_panel(4, ancho=2.4)])
        self.assertEqual([(f['line'], f['mensajes'], f.get('motivo')) for f in filas],
                         [(1, ['Ancho 2.4'], None), (2, [], None), (3, [], 'sistema')])
        self.assertIn('PRUEBA ENROLLABLE', filas[0]['descripcion'])
        # También una regla inactiva, y los errores que dependen de los datos.
        regla.write({'active': False, 'condition_code': "tela.name.lower() == 'x'"})
        filas = self.Line._probar_regla(regla, [self.linea(fabric_id=False, color_id=False)])
        self.assertTrue(filas[0].get('error'))

    def test_asistente_probar(self):
        regla = self.regla(message='Ancho {ancho}')
        quote = self.env['safra.quote'].create(
            {'partner_id': self.env['res.partner'].create({'name': 'Prueba reglas'}).id,
             'line_ids': [(0, 0, self.linea(width=2.4))]})
        wizard = self.env['safra.validation.rule.test'].create(
            {'rule_id': regla.id, 'quote_id': quote.id})
        wizard.action_probar()
        self.assertIn('Ancho 2.4', wizard.resultado)
        self.assertEqual(regla.action_probar()['res_model'], 'safra.validation.rule.test')


@tagged('post_install', '-at_install', 'safra')
class TestAjustesSprint17(SafraCommon):

    def test_kit_por_codigo_del_motor(self):
        Kit = self.env['safra.motor.kit']
        kit = Kit.create({'motor_value': '99', 'motor_name': 'Motor Prueba', 'tubo': 'R8',
                          'motor_ref_codes': 'ZTMOT1, ZTMOT2'})
        self.assertEqual(Kit.find_kit('ZTMOT2', 'R8'), kit)
        self.assertEqual(Kit.find_kit('99', 'R8'), kit)
        self.assertFalse(Kit.find_kit('ZTMOT', 'R8'))

    def test_motor_por_referencia_cuenta_como_motorizada(self):
        line = self.Line.new(self.linea(motor='I100002874'))
        self.assertTrue(line._con_motor())
        self.assertFalse(self.Line.new(self.linea(motor='0'))._con_motor())

    def test_ancho_minimo_del_motor(self):
        campo = self._campo('motor')
        if not campo.ref_category_id:
            return
        ref = self.env['safra.fabric'].create({'code': 'ZT-MOT', 'name': 'Motores Prueba',
                                               'category_id': campo.ref_category_id.id})
        motor = self._color(ref, 'ZTMOT', 'Motor Prueba', safra_u_ancho_min=1.0)
        line = self.Line.new(self.linea(motor=motor.code, width=0.9))
        self.assertEqual(line._motor_ancho_min(), 1.0)
        # Revisión 28-oct: sin dato vale 0; el valor por defecto va en la condición.
        self.assertEqual(self.Line.new(self.linea())._motor_ancho_min(), 0.0)

    def test_ancho_minimo_del_motor_por_defecto_en_la_condicion(self):
        regla = self.env['safra.validation.rule']._por_clave(['V_ANCHO_MIN_MOTOR'])
        regla.write({'momento': 'linea', 'condition_code': 'minimo = motor_ancho_min or 0.70\n'
                                                           'result = con_motor and ancho and ancho < minimo',
                     'message': 'E13095: El ancho mínimo para el motor seleccionado es de {minimo} metros.'})
        mensajes = [m['message'] for m in self.mensajes(
            [self.linea(width=0.65, height=1.0, has_motor=True, motor='M1')], 'V_ANCHO_MIN_MOTOR', cross=False)]
        self.assertEqual(mensajes, ['E13095: El ancho mínimo para el motor seleccionado es de 0.7 metros.'])
        self.assertFalse(self.mensajes([self.linea(width=0.75, height=1.0, has_motor=True, motor='M1')],
                                       'V_ANCHO_MIN_MOTOR', cross=False))

    def test_ajuste_motor_ancho_min(self):
        Param = self.env['ir.config_parameter'].sudo()
        regla = self.env['safra.validation.rule']._por_clave(['V_ANCHO_MIN_MOTOR'])
        regla.write({'condition_code': 'con_motor and ancho and ancho < motor_ancho_min',
                     'message': 'E13095: El ancho mínimo para el motor seleccionado es de {motor_ancho_min} metros.'})
        Param.set_param('website_quotes_safra.ajuste_motor_ancho_min', '')
        regla._ajuste_motor_ancho_min()
        self.assertIn('motor_ancho_min or 0.70', regla.condition_code)
        self.assertIn('{minimo}', regla.message)

    def test_control_compatible_por_referencia(self):
        """Con referencia de controles manda su columna «Motores (solo
        estos)», aunque el kit del motor permita otros controles."""
        campo = self._campo('motor')
        if not campo.ref_category_id:
            return
        ref = self.env['safra.fabric'].create({'code': 'ZT-MOT', 'name': 'Motores Prueba',
                                               'category_id': campo.ref_category_id.id})
        motor = self._color(ref, 'ZTMOT', 'Motor Prueba')
        self.env['safra.motor.kit'].create({'motor_value': '99', 'motor_name': 'Motor Prueba',
                                            'tubo': 'R8', 'motor_ref_codes': 'ZTMOT',
                                            'control_values': '22'})
        self.ctl_mono.motor_ids = motor.product_tmpl_id
        linea = self.linea(has_motor=True, motor=motor.code, control=self.ctl_mono._valor_control(),
                           width=1.5)
        self.assertNotIn('V_CONTROL_MOTOR', self.codigos([linea]))
        otro = self.env['product.template'].create({'name': 'Otro motor', 'safra_is_color': True})
        self.ctl_mono.motor_ids = otro
        self.assertIn('V_CONTROL_MOTOR', self.codigos([linea]))

    def test_peso_del_perfil_de_referencias(self):
        ref = self.env['safra.fabric'].create({'code': 'ZT-PER', 'name': 'Perfiles Prueba'})
        perfil = self._color(ref, 'ZTPER', 'Perfil Prueba', safra_u_peso=136)
        self.assertEqual(self.Line._peso_perfil(perfil.code), 136)
        self.assertEqual(self.Line._peso_perfil(False), 0.0)

    def test_ancho_de_telo_por_sistema(self):
        Track = self.env['safra.panel.track']
        self.assertEqual(Track._params(self.panel)['telo_min'], 0.35)
        self.panel.write({'panel_telo_min': 0.20, 'panel_telo_max': 0.475})
        p = Track._params(self.panel)
        self.assertEqual((p['telo_min'], p['telo_max']), (0.20, 0.475))
        # 6 telos en 1,80 m dan telos de unos 37 cm: con 0,475 pasa, en 2,40 no.
        self.assertIsNone(Track.revisar_libre(1.8, 0.08, 6, system=self.panel))
        self.assertTrue(Track.revisar_libre(3.2, 0.08, 6, system=self.panel))

    def test_doble_funcion_de_panel_duo(self):
        codigos = self.codigos([self.linea_panel(6, apertura='6', ancho=2.4)], cross=False)
        self.assertNotIn('V_PANEL_APERTURA', codigos)
        self.assertNotIn('V_PANEL_LAMAS', codigos)
        falla = self.mensajes([self.linea_panel(6, apertura='6', ancho=8.0)], 'V_PANEL_LAMAS',
                              cross=False)
        self.assertIn('apertura doble función', falla[0]['message'])

    def test_dependencias_de_cenefa_por_etiqueta(self):
        Field = self.env['safra.field']
        self.assertIn('eti:Cenefa en tela', Field._S14_TELA)
        self.assertIn('eti:METALICA', Field._S14_MET)
        line = self.Line.new({})
        self.assertTrue(line._depende_ok('I100002014', Field._S14_TELA, eti='Cenefa en tela'))
        self.assertFalse(line._depende_ok('054328', Field._S14_TELA, eti='PVC CLASICA'))

    def test_contexto_de_ejemplo(self):
        ctx = self.Line._contexto_ejemplo()
        for nombre in ('ancho', 'tela_2', 'estructura', 'lineas', 'otras_lineas', 'pedido',
                       'hallazgo', 'kit', 'motor_ancho_min', 'ancho_telo', 'width'):
            self.assertIn(nombre, ctx)


@tagged('post_install', '-at_install', 'safra')
class TestPortalSprint17(HttpCase, SafraCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        new_test_user(cls.env, login='safra_portal_s17', groups='base.group_portal')
        cls.env['safra.validation.rule'].sudo().create({
            'code': 'R_ANCHO', 'name': 'Ancho grande', 'severity': 'warning',
            'momento': 'campo', 'trigger_field_id': cls._campo('width').id,
            'system_ids': [(6, 0, cls.enrollable.ids)],
            'condition_code': 'ancho > 2', 'message': 'Con {ancho} m considere motor'})

    def setUp(self):
        super().setUp()
        self.authenticate('safra_portal_s17', 'safra_portal_s17')

    def test_validar_secuencia_desde_el_configurador(self):
        """Revisión 28-oct: «Aplicar» del configurador revisa las reglas «Al
        aplicar la secuencia» con los soportes propuestos y devuelve solo
        las de esa secuencia, con el índice de la persiana."""
        self.env['safra.validation.rule'].sudo().create({
            'code': 'R_SEC_MOTOR_INDEP', 'name': 'Motor sin INDEP', 'severity': 'error',
            'momento': 'secuencia',
            'condition_code': "'MOTOR' in (linea.soporte_izq, linea.soporte_der) and "
                              "'INDEP' in (linea.soporte_izq, linea.soporte_der)",
            'message': 'El motor no va con soporte independiente.'})
        base = {'system_id_%d': self.enrollable.id, 'fabric_id_%d': self.tela.id,
                'color_id_%d': self.blanco.id, 'width_%d': '1.5', 'height_%d': '1.8',
                'quantity_%d': '1', 'location_%d': 'Sala', 'same_header_%d': '1',
                'sequence_name_%d': 'S1'}
        datos = {}
        for idx in (0, 3):
            datos.update({k % idx: v for k, v in base.items()})
        datos.update({'soporte_izq_0': 'MOTOR', 'soporte_der_0': 'INDEP', 'has_motor_0': '1',
                      'soporte_izq_3': 'INDEP', 'soporte_der_3': 'TERMINAL',
                      'secuencia_nombre': 'S1'})
        issues = self.make_jsonrpc_request('/cotizador/ajax/validar_secuencia', datos)
        self.assertEqual([(i['code'], i['idx']) for i in issues], [('R_SEC_MOTOR_INDEP', 0)])
        datos['soporte_der_0'] = datos['soporte_izq_3'] = 'DEP'
        self.assertFalse(self.make_jsonrpc_request('/cotizador/ajax/validar_secuencia', datos))

    def test_config_y_validar_campo(self):
        config = self.make_jsonrpc_request('/cotizador/ajax/config', {'system_id': self.enrollable.id})
        self.assertEqual(config['reglas_campo'], ['width'])
        datos = {'system_id_0': self.enrollable.id, 'fabric_id_0': self.tela.id,
                 'color_id_0': self.blanco.id, 'width_0': '2.4', 'height_0': '1.8',
                 'quantity_0': '1', 'location_0': 'Sala'}
        issues = self.make_jsonrpc_request('/cotizador/ajax/validar_campo', dict(datos, campo='width'))
        self.assertEqual([(i['severity'], i['message']) for i in issues],
                         [('warning', 'Con 2.4 m considere motor [R_ANCHO]')])
        self.assertFalse(self.make_jsonrpc_request('/cotizador/ajax/validar_campo',
                                                   dict(datos, campo='height')))
        # Se revisa apenas se digita, aunque todavía no haya tela.
        sin_tela = dict(datos, campo='width', fabric_id_0='', color_id_0='')
        self.assertEqual([i['code'] for i in self.make_jsonrpc_request(
            '/cotizador/ajax/validar_campo', sin_tela)], ['R_ANCHO'])


@tagged('post_install', '-at_install', 'safra')
class TestReglasSafra17(SafraCommon):
    """Las validaciones del archivo de Safra sembradas como reglas."""

    def test_todas_las_reglas_se_pueden_guardar_y_evaluar(self):
        from ..models import safra_reglas_17 as R17
        Rule = self.env['safra.validation.rule'].sudo()
        ctx = self.Line._contexto_ejemplo()
        from ..models.safra_panel import evaluar_formula
        for r in R17.REGLAS:
            regla = Rule.new({'code': r['code'], 'name': r['name'],
                              'condition_code': r['condition'], 'message': r['message']})
            self.assertFalse(regla._revisar_condicion(), r['code'])
            evaluar_formula(r['condition'], dict(ctx))

    def test_requiere_motor_fuera_de_la_tabla_manual(self):
        # La tabla manual del enrollable de prueba llega a 2,00 m con R8 y la
        # motorizada también: a 2,00 m manual pasa; sin regla manual pero con
        # motorizada pide motor.
        self.r16.drive_type = 'motor'
        self.r24.drive_type = 'motor'
        codigos = self.codigos([self.linea(width=2.4)], cross=False)
        self.assertIn('V_REQUIERE_MOTOR', codigos)
        self.assertNotIn('V_ESTRUCTURA', codigos)

    def test_telas_4_y_5_y_aumento_de_tela(self):
        line = self.Line.new(self.linea(attribute_values={'fabric_id_4': self.tela_sheer.id,
                                                          'color_id_4': self.sheer.id}))
        ctx = line._contexto_reglas(1, [], {})
        self.assertEqual(ctx['tela_4'], self.tela_sheer)
        self.assertEqual(ctx['color_4'], self.sheer)
        self.assertFalse(ctx['tela_5'])
        self.assertEqual(ctx['estructura']['aumento_tela'], 0.25)


@tagged('post_install', '-at_install', 'safra')
class TestCorteTela(SafraCommon):
    """Archivos de Safra «Tipos de corte tela» (26-oct): corte normal,
    atravesado y añadido en persianas; bajo falso y paños en cortinas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from ..models import safra_reglas_17 as R17
        Param = cls.env['ir.config_parameter'].sudo()
        Param.set_param('safra.corte.constante_tubo', 'R8:0.17, R16:0.20, R24:0.20')
        Rule = cls.env['safra.validation.rule'].sudo().with_context(active_test=False)
        for code, (nombre, _c, cond, _m, msg, _s, _sis) in R17.CORTE_TELA.items():
            vals = {'condition_code': cond, 'message': msg, 'active': True,
                    'momento': 'linea', 'system_ids': [(5, 0, 0)]}
            regla = Rule.search([('code', '=', code)])
            if regla:
                regla.write(vals)
            else:
                Rule.create(dict(vals, code=code, name=nombre))
        Rule.search([('code', '=', 'V_ANADIDO')]).severity = 'warning'
        # Las fórmulas del corte de las cortinas como las deja el módulo.
        Param.search([('key', 'in', list(R17.FORMULAS_CORTE_CORTINA))]).unlink()
        cls.cortina = cls._sistema('ZT49', 'PRUEBA CORTINA',
                                   ['width', 'height', 'quantity', 'location', 'fabric_id', 'color_id'],
                                   (0.30, 11.8, 0.30, 5.0))
        cls.cortina.factor_confeccion = 2.8
        cls.enrollable.calculo_corte = 'persiana'
        cls.cortina.calculo_corte = 'cortina'
        cls.tela.system_ids = [(4, cls.cortina.id)]

    def corte(self, **vals):
        return self.Line.new(self.linea(**vals))._corte_tela()

    def test_persiana_normal_y_no_atravesable(self):
        self.assertEqual(self.corte(width=2.4)['tipo'], 'normal')
        corte = self.corte(width=2.6)
        self.assertEqual(corte['tipo'], 'no_fabricable')
        self.assertIn('no es atravesable', corte['motivo'])
        # Marcar Añadido no cambia nada si la tela no es atravesable.
        self.tela.write({'is_anadido': True})
        self.assertEqual(self.corte(width=2.6)['tipo'], 'no_fabricable')
        self.assertIn('V_ANCHO_ROLLO', self.codigos([self.linea(width=2.6)], cross=False))

    def test_persiana_atravesada(self):
        # 2,60 m va con R16 (constante 0,20): alto 2,20 + 0,20 cabe en el rollo de 2,50.
        self.tela.pierceable_type = 'si'
        corte = self.corte(width=2.6, height=2.2)
        self.assertEqual((corte['tipo'], corte['constante']), ('atravesado', 0.2))
        issues = self.mensajes([self.linea(width=2.6, height=2.2)], 'V_CORTE_ATRAVESADO', cross=False)
        self.assertEqual(len(issues), 1)
        self.assertIn('rollo (2.5 m), la tela Tela Prueba se cortará atravesada', issues[0]['message'])
        self.assertNotIn('V_CORTE_ATRAVESADO', self.codigos(
            [self.linea(width=2.6, height=2.2, acepta_atravesado=True)], cross=False))
        # «Sí cliente» funciona igual.
        self.tela.pierceable_type = 'si_cliente'
        self.assertEqual(self.corte(width=2.6, height=2.2)['tipo'], 'atravesado')

    def test_persiana_con_anadido(self):
        self.tela.write({'pierceable_type': 'si', 'is_anadido': True})
        # Alto 2,60 + 0,20 no cabe atravesado: un añadido (≤ 2 × 2,50 − 0,20 = 4,80).
        corte = self.corte(width=2.6, height=2.6)
        self.assertEqual((corte['tipo'], corte['anadidos']), ('anadido', 1))
        issues = self.mensajes([self.linea(width=2.6, height=2.6)], 'V_ANADIDO', cross=False)
        self.assertEqual([i['severity'] for i in issues], ['warning'])
        self.assertEqual(self.corte(width=2.6, height=4.8)['tipo'], 'anadido')
        # 4,90 m pasa del límite: dos añadidos y la tela permite uno.
        corte = self.corte(width=2.6, height=4.9)
        self.assertEqual((corte['tipo'], corte['anadidos'], corte['maximo_anadidos']),
                         ('anadido_excede', 2, 1))
        self.assertIn('V_ANADIDO_MAXIMO', self.codigos([self.linea(width=2.6, height=4.9)], cross=False))
        # Con máximo 2 en la referencia sí pasa.
        self.tela.max_anadidos = 2
        self.assertEqual(self.corte(width=2.6, height=4.9)['tipo'], 'anadido')

    def test_persiana_atravesable_sin_anadido(self):
        self.tela.pierceable_type = 'si'
        corte = self.corte(width=2.6, height=2.6)
        self.assertEqual(corte['tipo'], 'no_fabricable')
        self.assertIn('no permite añadido', corte['motivo'])

    def test_constante_de_tubo_no_listado(self):
        # R24 está en la tabla; un tubo que no está usa el aumento de la estructura.
        self.assertEqual(self.Line._constante_tubo('R24', 0.28), 0.2)
        self.assertEqual(self.Line._constante_tubo('Tubo 3', 0.4), 0.4)

    def cortina_corte(self, **vals):
        return self.corte(**dict({'system_id': self.cortina.id, 'width': 2.0}, **vals))

    def test_cortina_normal_bajo_falso_y_panos(self):
        # Rollo 2,50: normal si alto + 0,06 + 0,21 − 0,035 ≤ 2,50 (alto ≤ 2,265).
        self.assertEqual(self.cortina_corte(height=2.2)['tipo'], 'normal')
        # Bajo falso hasta 2,50 + 0,12.
        self.assertEqual(self.cortina_corte(height=2.6)['tipo'], 'bajo_falso')
        # Más alto: paños solo si la tela los permite (Añadido).
        self.assertEqual(self.cortina_corte(height=3.0)['tipo'], 'no_fabricable')
        self.tela.is_anadido = True
        corte = self.cortina_corte(height=3.0)
        # 2,00 × 2,8 = 5,60 m de tela ÷ 2,50 → 3 paños.
        self.assertEqual((corte['tipo'], corte['panos'], corte['ancho_tela']), ('panos', 3, 5.6))

    def test_cortina_atravesable_primero_bajo_falso_luego_panos(self):
        """Reunión 30-oct (fila 143, punto 5): la tela atravesable sigue el
        mismo orden que la que no lo es (bajo falso y luego paños) y, en
        cortinas, atravesar es cortar por paños aunque no tenga Añadido."""
        self.tela.pierceable_type = 'si'
        self.assertEqual(self.cortina_corte(height=2.2)['tipo'], 'normal')
        self.assertEqual(self.cortina_corte(height=2.6)['tipo'], 'bajo_falso')
        corte = self.cortina_corte(height=3.0)
        self.assertEqual((corte['tipo'], corte['panos']), ('panos', 3))
        # Sin Añadido ni atravesable, no se puede fabricar.
        self.tela.pierceable_type = 'no'
        self.assertEqual(self.cortina_corte(height=3.0)['tipo'], 'no_fabricable')

    def regla_panos(self):
        from ..models import safra_reglas_17 as R17
        r = R17.CORTE_PANOS
        return self.env['safra.validation.rule'].create({
            'code': r['code'], 'name': r['name'], 'severity': r['severity'],
            'momento': r['momento'], 'condition_code': r['condition'], 'message': r['message']})

    def test_cortina_panos_pide_la_aceptacion(self):
        """Reunión 30-oct (fila 143, puntos 4 y 6): con corte por paños sale
        el aviso de paños (no el de atravesado), con cualquier ancho, y no se
        guarda la línea hasta marcar la aceptación; el resto del formulario
        no se bloquea."""
        self.env['safra.validation.rule'].search([('code', '=', 'V_CORTE_PANOS')]).unlink()
        self.regla_panos()
        self.tela.pierceable_type = 'si'
        for ancho in (1.0, 3.0):
            vals = self.linea(system_id=self.cortina.id, width=ancho, height=3.0)
            avisos = self.Line._avisos_corte(vals)
            self.assertEqual([a['code'] for a in avisos['avisos']], ['V_CORTE_PANOS'])
            self.assertIn('se cortará a paños (ancho del rollo: 2.5 m)', avisos['avisos'][0]['message'])
            self.assertFalse(avisos['bloquea'])
            self.assertIn('V_CORTE_PANOS', self.codigos([vals], cross=False))
            aceptada = dict(vals, acepta_atravesado=True)
            self.assertFalse(self.Line._avisos_corte(aceptada)['avisos'])
            self.assertNotIn('V_CORTE_PANOS', self.codigos([aceptada], cross=False))
        # Con bajo falso no se pide.
        self.assertFalse(self.Line._avisos_corte(
            self.linea(system_id=self.cortina.id, width=2.0, height=2.6))['avisos'])

    def test_ajuste_corte_panos(self):
        from ..models import safra_reglas_17 as R17
        Param = self.env['ir.config_parameter'].sudo()
        Param.search([('key', '=', 'website_quotes_safra.ajuste_corte_panos')]).unlink()
        self.env['safra.validation.rule'].search([('code', '=', 'V_CORTE_PANOS')]).unlink()
        Param.set_param('safra.formula.cortina_bajo_falso', R17.CORTINA_BAJO_FALSO_ANTERIOR)
        Param.set_param('safra.formula.cortina_normal', 'result = alto <= ancho_rollo')
        self.env['safra.validation.rule']._ajuste_corte_panos()
        regla = self.env['safra.validation.rule']._por_clave(['V_CORTE_PANOS'])
        self.assertEqual((regla.severity, regla.momento), ('error', 'linea'))
        self.assertEqual(Param.get_param('safra.formula.cortina_bajo_falso'),
                         R17.FORMULAS_CORTE_CORTINA['safra.formula.cortina_bajo_falso'])
        # Una fórmula cambiada a mano se respeta.
        self.assertEqual(Param.get_param('safra.formula.cortina_normal'), 'result = alto <= ancho_rollo')

    def test_ajuste_etiqueta_panos(self):
        """Reunión 3-nov: el check de las cortinas dice que el cliente acepta
        los paños; una etiqueta propia se respeta."""
        from ..models import safra_reglas_17 as R17
        Param = self.env['ir.config_parameter'].sudo()
        campo = self._campo('acepta_atravesado')
        cortinas = self.env['safra.system'].search([('code', 'in', list(R17.CORTE_PANOS['systems']))])
        if not cortinas or not campo:
            self.skipTest('La base no tiene las cortinas 49/57 o el campo de aceptación')
        Mapping = self.env['safra.system.field']
        mappings = Mapping.search([('system_id', 'in', cortinas.ids), ('field_id', '=', campo.id)])
        for sistema in cortinas - mappings.mapped('system_id'):
            mappings |= Mapping.create({'system_id': sistema.id, 'field_id': campo.id})
        mappings.write({'label_override': R17.CORTE_PANOS_ETIQUETA_ANTERIOR, 'help_override': False})
        propia = mappings[1:2]
        propia.write({'label_override': 'Etiqueta propia', 'help_override': 'Ayuda propia'})
        Param.search([('key', '=', 'website_quotes_safra.ajuste_etiqueta_panos')]).unlink()
        self.env['safra.validation.rule']._ajuste_etiqueta_panos()
        self.assertEqual((mappings[0].label_override, mappings[0].help_override),
                         (R17.CORTE_PANOS_ETIQUETA, R17.CORTE_PANOS_AYUDA))
        if propia:
            self.assertEqual((propia.label_override, propia.help_override), ('Etiqueta propia', 'Ayuda propia'))
