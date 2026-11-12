# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import CAMPOS_ENROLLABLE, SafraCommon


class Ajustes15OctCommon(SafraCommon):
    """Reunión 15-oct (ajustes Sprint 1.3: cabezal y ficha técnica).
    Sistema propio con tubos que no existen en la base (ZTUBO1 y ZTUBO2),
    un campo de perfil y uno de cabezal con categorías de prueba."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sistema = cls._sistema('ZT15', 'PRUEBA 15 OCT', CAMPOS_ENROLLABLE,
                                   (0.30, 3.00, 0.30, 4.00))
        cls.tela.system_ids |= cls.sistema
        cls.tela_pesada.system_ids |= cls.sistema
        Rule = cls.env['safra.structure.rule']
        sistemas = [(6, 0, cls.sistema.ids)]
        cls.tubo1 = Rule.create({'system_ids': sistemas, 'drive_type': 'any',
                                 'width_from': 0.30, 'width_to': 2.00, 'tubo': 'ZTUBO1',
                                 'mecanismo': 'ZTM1', 'soporte': 'ZTS1', 'terminal': 'ZTT1'})
        cls.tubo2 = Rule.create({'system_ids': sistemas, 'drive_type': 'any',
                                 'width_from': 2.001, 'width_to': 3.00, 'tubo': 'ZTUBO2',
                                 'mecanismo': 'ZTM2'})
        Option = cls.env['safra.product.option']
        cls.opt_tubo1 = Option.search([('type', '=', 'tubo'), ('name', '=', 'ZTUBO1')])
        cls.opt_tubo2 = Option.search([('type', '=', 'tubo'), ('name', '=', 'ZTUBO2')])
        Fabric, Color = cls.env['safra.fabric'], cls.env['safra.fabric.color']
        seccion = cls._campo('perfil').section_id.id

        # Perfil (fila 50): una referencia que solo sirve con Tela Prueba.
        cat_perfil = Option.create({'name': 'Perfil prueba', 'type': 'ref_categoria'})
        cls.campo_perfil = cls.env['safra.field'].create({
            'code': 'zt_perfil', 'name': 'Perfil prueba', 'field_type': 'ref_categoria',
            'ref_category_id': cat_perfil.id, 'section_id': seccion})
        cls.ref_perfil = Fabric.create({'code': 'ZT-PERF', 'name': 'Perfil Prueba',
                                        'category_id': cat_perfil.id,
                                        'tela_ids': [(6, 0, cls.tela.ids)]})
        cls.perfil = Color.create({'fabric_id': cls.ref_perfil.id, 'code': 'ZTPERF',
                                   'name': 'Perfil Estándar'})

        # Cabezal (fila 68): el cuadrado solo se fabrica con ZTUBO1.
        cat_cab = Option.create({'name': 'Cabezal prueba', 'type': 'ref_categoria'})
        cls.campo_cabezal = cls.env['safra.field'].create({
            'code': 'zt_cabezal', 'name': 'Cabezal prueba', 'field_type': 'ref_categoria',
            'ref_category_id': cat_cab.id, 'section_id': seccion})
        ref_cab = Fabric.create({'code': 'ZT-CAB', 'name': 'Cabezales Prueba',
                                 'category_id': cat_cab.id})
        cls.prod_cuadrado = cls.env['product.template'].create({
            'name': 'Cabezal Cuadrado Prueba', 'safra_code': 'ZTCUAD', 'safra_is_color': True,
            'is_storable': True, 'safra_tubo_ids': [(6, 0, cls.opt_tubo1.ids)]})
        cls.cuadrado = Color.create({'fabric_id': ref_cab.id,
                                     'product_tmpl_id': cls.prod_cuadrado.id})

        cls.env['safra.system.field'].create([
            {'system_id': cls.sistema.id, 'field_id': campo.id, 'sequence': 900}
            for campo in (cls.campo_perfil, cls.campo_cabezal)])
        # Fila 74: «Pedido sin restricciones» en todos los sistemas.
        cls.env['safra.field']._apply_15oct()

    def linea15(self, **vals):
        return self.linea(system_id=self.sistema.id, **vals)

    def entrar_stock(self, producto, cantidad):
        almacen = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        self.env['stock.quant']._update_available_quantity(
            producto.product_variant_id, almacen.lot_stock_id, cantidad)
        # Las existencias no se guardan en el producto: se recalculan.
        self.env.invalidate_all()


@tagged('post_install', '-at_install', 'safra')
class TestAjustes15Oct(Ajustes15OctCommon):

    # --- Fila 59: «Tipo cabezal» fuera de Estructura por Ancho -----------

    def test_tipo_cabezal_fuera_del_formulario(self):
        for xmlid in ('view_safra_structure_rule_form', 'view_safra_structure_rule_tree',
                      'view_safra_structure_rule_search'):
            arch = self.env.ref('website_quotes_safra.%s' % xmlid).arch
            self.assertNotIn('cabezal_type', arch, xmlid)

    # --- Fila 50: perfil solo con ciertas telas --------------------------

    def test_perfil_solo_con_sus_telas(self):
        self.assertNotIn('V_OPCION_TELA', self.codigos(
            [self.linea15(attribute_values={'zt_perfil': 'ZTPERF'})], cross=False))
        otra = self.mensajes([self.linea15(fabric_id=self.tela_pesada.id,
                                           color_id=self.pesada.id,
                                           attribute_values={'zt_perfil': 'ZTPERF'})],
                             'V_OPCION_TELA', cross=False)
        self.assertEqual(len(otra), 1)
        self.assertIn('Tela Pesada', otra[0]['message'])

    def test_perfil_sin_telas_sirve_para_todas(self):
        self.ref_perfil.tela_ids = False
        self.assertNotIn('V_OPCION_TELA', self.codigos(
            [self.linea15(fabric_id=self.tela_pesada.id, color_id=self.pesada.id,
                          attribute_values={'zt_perfil': 'ZTPERF'})], cross=False))

    # --- Fila 68: tubo sin insumos y opciones por tubo -------------------

    def test_tubos_como_opciones(self):
        """Cada tubo de la tabla queda como opción «Tubo» para el maestro."""
        self.assertTrue(self.opt_tubo1 and self.opt_tubo2)
        self.tubo2.tubo = 'ZTUBO3'
        self.assertTrue(self.env['safra.product.option'].search(
            [('type', '=', 'tubo'), ('name', '=', 'ZTUBO3')]))

    def test_tubo_bloqueado_sin_stock_y_se_reactiva(self):
        Rule = self.env['safra.structure.rule']
        soporte = self.env['product.template'].create({
            'name': 'Soporte ZTUBO2 Prueba', 'is_storable': True,
            'safra_tubo_ids': [(6, 0, self.opt_tubo2.ids)]})
        self.assertEqual(list(Rule.tubos_bloqueados(['ZTUBO1', 'ZTUBO2'])), ['ZTUBO2'])
        self.assertIn('V_TUBO_SIN_INSUMO', self.codigos([self.linea15(width=2.5)], cross=False))
        self.assertNotIn('V_TUBO_SIN_INSUMO', self.codigos([self.linea15(width=1.5)], cross=False))
        self.entrar_stock(soporte, 5)
        self.assertFalse(Rule.tubos_bloqueados(['ZTUBO2']))
        self.assertNotIn('V_TUBO_SIN_INSUMO', self.codigos([self.linea15(width=2.5)], cross=False))

    def test_opcion_del_portal_no_bloquea_el_tubo(self):
        """El cabezal sin stock no bloquea el tubo: es una opción del
        portal, se filtra aparte."""
        self.assertFalse(self.env['safra.structure.rule'].tubos_bloqueados(['ZTUBO1']))

    def test_cabezal_solo_con_sus_tubos(self):
        valor = self.cuadrado.code
        self.assertNotIn('V_OPCION_TUBO', self.codigos(
            [self.linea15(width=1.5, attribute_values={'zt_cabezal': valor})], cross=False))
        self.assertIn('V_OPCION_TUBO', self.codigos(
            [self.linea15(width=2.5, attribute_values={'zt_cabezal': valor})], cross=False))

    def test_unificacion_a_un_tubo_bloqueado(self):
        """Unificar a un tubo sin insumos también se bloquea."""
        self.env['product.template'].create({
            'name': 'Tubo ZTUBO2 Prueba', 'is_storable': True,
            'safra_tubo_ids': [(6, 0, self.opt_tubo2.ids)]})
        self.assertIn('V_TUBO_SIN_INSUMO', self.codigos(
            [self.linea15(width=1.5, attribute_values={'unificacion_mando': 'ZTUBO2'})],
            cross=False))

    # --- Acta del 30-oct (Tubo, punto 8): la disponibilidad en el menú ----

    def soporte_sin_stock(self):
        return self.env['product.template'].create({
            'name': 'Soporte ZTUBO2 Prueba', 'is_storable': True,
            'safra_tubo_ids': [(6, 0, self.opt_tubo2.ids)]})

    def regla_tubo(self):
        return self.env['safra.validation.rule']._por_clave(['V_TUBO_SIN_INSUMO'])[:1]

    def test_tubo_sin_insumo_con_condicion_y_mensaje_del_menu(self):
        self.assertEqual(self.regla_tubo().condition_code, 'bool(insumos_sin_stock)')
        self.soporte_sin_stock()
        self.assertEqual([i['message'] for i in self.mensajes(
            [self.linea15(width=2.5)], 'V_TUBO_SIN_INSUMO', cross=False)],
            ['E20038: El tubo ZTUBO2 no está disponible: no hay existencias de Soporte ZTUBO2 Prueba.'])
        # Safra cambia el mensaje y la severidad en Validaciones.
        self.regla_tubo().write({'message': 'Sin existencias: {insumos_sin_stock}', 'severity': 'warning'})
        avisos = self.mensajes([self.linea15(width=2.5)], 'V_TUBO_SIN_INSUMO', cross=False)
        self.assertEqual([(a['message'], a['severity']) for a in avisos],
                         [('Sin existencias: Soporte ZTUBO2 Prueba', 'warning')])

    def test_tubo_sin_insumo_la_condicion_se_puede_cambiar(self):
        self.soporte_sin_stock()
        self.regla_tubo().condition_code = 'bool(insumos_sin_stock) and ancho > 2.8'
        self.assertFalse(self.mensajes([self.linea15(width=2.5)], 'V_TUBO_SIN_INSUMO', cross=False))
        self.assertTrue(self.mensajes([self.linea15(width=2.9)], 'V_TUBO_SIN_INSUMO', cross=False))

    def test_ajuste_del_tubo_sin_insumo_respeta_lo_editado(self):
        Param = self.env['ir.config_parameter'].sudo()
        marca = 'website_quotes_safra.ajuste_tubo_sin_insumo'
        Rule = self.env['safra.validation.rule']
        self.regla_tubo().write({'condition_code': 'hallazgo', 'message': False})
        Param.set_param(marca, '')
        Rule._ajuste_tubo_sin_insumo()
        self.assertEqual(self.regla_tubo().condition_code, 'bool(insumos_sin_stock)')
        self.assertIn('{insumos_sin_stock}', self.regla_tubo().message)
        self.regla_tubo().condition_code = 'bool(insumos_sin_stock) and alto > 3'
        Param.set_param(marca, '')
        Rule._ajuste_tubo_sin_insumo()
        self.assertEqual(self.regla_tubo().condition_code, 'bool(insumos_sin_stock) and alto > 3')

    # --- Fila 74: pedido sin restricciones -------------------------------

    def test_campo_en_la_ficha_tecnica_solo_para_el_grupo(self):
        self.env['safra.field']._apply_15oct()
        campo = self._campo('sin_restricciones')
        self.assertEqual(campo.section_id.code, 'ficha')
        self.assertEqual(campo.group_id,
                         self.env.ref('website_quotes_safra.group_safra_sin_restricciones'))
        self.assertTrue(self.env['safra.system.field'].search_count(
            [('system_id', '=', self.sistema.id), ('field_id', '=', campo.id)]))

    def test_errores_pasan_a_advertencia(self):
        normal = self.mensajes([self.linea15(width=3.5)], 'V_RANGO_ANCHO')
        self.assertEqual(normal[0]['severity'], 'error')
        sin = self.mensajes([self.linea15(width=3.5, sin_restricciones=True)], 'V_RANGO_ANCHO')
        self.assertEqual(sin[0]['severity'], 'warning')
        self.assertTrue(sin[0]['saltada'])
        self.assertTrue(sin[0]['message'].startswith('Sin restricciones'))
        todos = self.validar([self.linea15(width=3.5, sin_restricciones=True)])
        self.assertFalse([i for i in todos if i['severity'] == 'error'])

    def test_aprobacion_de_produccion(self):
        cliente = self.env['res.partner'].create({'name': 'Distribuidor 15 Oct'})
        quote = self.env['safra.quote'].create({
            'partner_id': cliente.id,
            'line_ids': [(0, 0, dict(self.linea15(width=3.5), sequence=10,
                                     sin_restricciones=True,
                                     sin_restricciones_detalle='OB0005: ancho fuera de rango'))],
        })
        ticket = quote._create_production_ticket()
        self.assertTrue(ticket.safra_sin_restricciones)
        self.assertEqual(quote.line_ids.production_ticket_id, ticket)
        self.assertIn('ancho fuera de rango', ticket.description)
        quote._update_design_state()
        self.assertEqual(quote.state, 'pending_production')
        with self.assertRaises(UserError):
            quote.action_confirm()
        ticket.action_safra_approve_production()
        self.assertTrue(ticket.safra_produccion_aprobada)
        self.assertEqual(quote.state, 'production_approved')
        # Al confirmar se revalida: la persiana aprobada no se anula.
        quote.action_confirm()
        self.assertEqual(quote.state, 'confirmed')


@tagged('post_install', '-at_install', 'safra')
class TestPortalAjustes15Oct(HttpCase, Ajustes15OctCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usuario = new_test_user(cls.env, login='safra_15oct_prueba',
                                    groups='base.group_portal')

    def setUp(self):
        super().setUp()
        self.authenticate('safra_15oct_prueba', 'safra_15oct_prueba')

    def rpc(self, ruta, **params):
        return self.make_jsonrpc_request(ruta, params)

    def formulario(self, **extra):
        form = {'system_id_0': self.sistema.id, 'fabric_id_0': self.tela.id,
                'color_id_0': self.blanco.id, 'width_0': '3.5', 'height_0': '1.8',
                'quantity_0': '1', 'location_0': 'Sala'}
        form.update(extra)
        return form

    def test_opciones_con_telas_y_tubos(self):
        config = self.rpc('/cotizador/ajax/config', system_id=self.sistema.id)
        campos = {f['code']: f for f in config['fields']}
        perfil = campos['zt_perfil']['options'][0]
        self.assertEqual(perfil['telas'], self.tela.ids)
        self.assertEqual(perfil['sin_telas'], [])
        # Reunión 28-oct: telas no compatibles con la línea.
        self.perfil.tela_excluida_ids = self.tela
        config = self.rpc('/cotizador/ajax/config', system_id=self.sistema.id)
        campos = {f['code']: f for f in config['fields']}
        self.assertEqual(campos['zt_perfil']['options'][0]['sin_telas'], self.tela.ids)
        cabezal = campos['zt_cabezal']['options'][0]
        self.assertEqual(cabezal['tubos'], ['ZTUBO1'])

    def test_tubo_bloqueado_en_la_ficha(self):
        self.env['product.template'].create({
            'name': 'Soporte ZTUBO2 Portal', 'is_storable': True,
            'safra_tubo_ids': [(6, 0, self.opt_tubo2.ids)]})
        res = self.rpc('/cotizador/ajax/precio', fabric_id=self.tela.id, width=1.5,
                       height=1.8, system_id=self.sistema.id)
        self.assertEqual(res['tubo']['mayores'], [])
        self.assertIn('ZTUBO2', res['tubo']['bloqueados'])
        self.assertEqual(res['mechanism'], 'Tubo: ZTUBO1 - Mecanismo: ZTM1 - Cabezal: No aplica')

    def test_aviso_del_tubo_en_la_ficha_desde_validaciones(self):
        self.env['product.template'].create({
            'name': 'Soporte ZTUBO2 Portal', 'is_storable': True,
            'safra_tubo_ids': [(6, 0, self.opt_tubo2.ids)]})
        res = self.rpc('/cotizador/ajax/corte_tela', **self.formulario(width_0='2.5'))
        self.assertEqual([a['message'] for a in res['avisos_ficha']], [
            'E20038: El tubo ZTUBO2 no está disponible: no hay existencias de Soporte ZTUBO2 Portal.'
            ' [V_TUBO_SIN_INSUMO]'])
        # No va con los avisos de la tela ni bloquea el formulario.
        self.assertFalse([a for a in res['avisos'] if a['code'] == 'V_TUBO_SIN_INSUMO'])
        self.assertFalse(res['bloquea'])
        # Con existencias del tubo de 1,50 m (ZTUBO1) no hay aviso.
        res = self.rpc('/cotizador/ajax/corte_tela', **self.formulario(width_0='1.5'))
        self.assertEqual(res['avisos_ficha'], [])

    def test_opcion_sin_stock_en_gris(self):
        # Con mínimo de stock en la referencia del cabezal y sin existencias,
        # el cabezal sigue en la lista pero sin stock (antes no salía).
        self.cuadrado.fabric_id.cant_min_stock = 1
        config = self.rpc('/cotizador/ajax/config', system_id=self.sistema.id)
        cabezal = {f['code']: f for f in config['fields']}['zt_cabezal']['options']
        self.assertEqual([(o['value'], o['available']) for o in cabezal], [(self.cuadrado.code, 0)])
        self.entrar_stock(self.prod_cuadrado, 3)
        config = self.rpc('/cotizador/ajax/config', system_id=self.sistema.id)
        cabezal = {f['code']: f for f in config['fields']}['zt_cabezal']['options']
        self.assertEqual([o['available'] for o in cabezal], [1])

    def test_sin_restricciones_pasa_a_la_verificacion(self):
        """Reunión 09-nov (fila 74): «Pedido sin restricciones» ya no sale en
        el portal; la verificación de fabricación hace que las restricciones
        no bloqueen."""
        self.env['safra.field']._ajuste_unificar_verificacion()
        config = self.rpc('/cotizador/ajax/config', system_id=self.sistema.id)
        self.assertNotIn('sin_restricciones', {f['code'] for f in config['fields']})
        form = self.formulario(requiere_verificacion='1', verificacion_observaciones='Revisar')
        errores = [i for i in self.rpc('/cotizador/ajax/validar', **form)
                   if i['code'] == 'V_RANGO_ANCHO']
        self.assertEqual(errores[0]['severity'], 'error')
        self.usuario.group_ids |= self.env.ref('website_quotes_safra.group_safra_verificacion')
        errores = [i for i in self.rpc('/cotizador/ajax/validar', **form)
                   if i['code'] == 'V_RANGO_ANCHO']
        self.assertEqual(errores[0]['severity'], 'warning')


class PendienteSprint12Common(SafraCommon):
    """Pendiente del Sprint 1.2 (reunión 13-oct, comentario del 15-oct): las
    asociaciones de control, motor y sistema van en Referencias."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Option, Fabric, Color = (cls.env['safra.product.option'], cls.env['safra.fabric'],
                                 cls.env['safra.fabric.color'])
        Product = cls.env['product.template']
        cls.cat_motor = Option.create({'name': 'Motor prueba', 'type': 'ref_categoria',
                                       'es_motor': True})
        cls.item_rf = Product.create({'name': 'Receptor RF Prueba'})
        cls.item_cargador = Product.create({'name': 'Cargador Prueba'})
        cls.control_maestro = Product.create({'name': 'Control Maestro Prueba',
                                              'safra_is_color': True})
        # En el maestro el motor dice lo contrario que su línea: manda la línea.
        cls.prod_motor = Product.create({
            'name': 'Motor Bateria Prueba', 'safra_code': 'ZTMOT', 'safra_is_color': True,
            'safra_u_requiere_interruptor_rf': False, 'safra_u_requiere_cargador': False,
            'safra_u_control_ids': [(6, 0, cls.control_maestro.ids)]})
        ref = Fabric.create({'code': 'ZT-MOTORES', 'name': 'Motores Prueba',
                             'category_id': cls.cat_motor.id})
        cls.motor = Color.create({
            'fabric_id': ref.id, 'product_tmpl_id': cls.prod_motor.id,
            'requiere_rf': True, 'rf_item_id': cls.item_rf.id,
            'requiere_cargador': True, 'cargador_item_id': cls.item_cargador.id})


@tagged('post_install', '-at_install', 'safra')
class TestPendienteSprint12(PendienteSprint12Common):

    def test_motor_desde_el_maestro_una_vez(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('website_quotes_safra.motores_desde_maestro', False)
        self.prod_motor.write({'safra_u_requiere_interruptor_rf': True,
                               'safra_u_interruptor_item_id': self.item_rf.id,
                               'safra_u_requiere_cargador': False})
        self.env['safra.fabric.color']._motores_desde_maestro()
        self.assertEqual((self.motor.requiere_rf, self.motor.rf_item_id, self.motor.requiere_cargador),
                         (True, self.item_rf, False))
        # Después lo administra Safra en la referencia.
        self.motor.requiere_cargador = True
        self.env['safra.fabric.color']._motores_desde_maestro()
        self.assertTrue(self.motor.requiere_cargador)

    def test_maestro_sin_campos_repetidos(self):
        arch = self.env.ref('website_quotes_safra.product_template_form_parametrizacion').arch
        for campo in ('safra_tela_atravesable', 'safra_u_bolsillo', 'safra_permite_corte_entera',
                      'safra_u_control_ids', 'safra_u_requiere_interruptor_rf',
                      'safra_u_requiere_cargador',
                      # Revisión de campos repetidos (27-oct).
                      # Carga, diámetro, espacio y aumento del tubo volvieron: la
                      # Estructura por Ancho los toma de las Referencias (revisión
                      # cálculo de tubo, punto 1.1).
                      'safra_is_tela', 'safra_cant_min_stock', 'safra_asociacion_ids'):
            self.assertNotIn('name="%s"' % campo, arch, campo)


@tagged('post_install', '-at_install', 'safra')
class TestPortalPendienteSprint12(HttpCase, PendienteSprint12Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usuario = new_test_user(cls.env, login='safra_12pend_prueba',
                                    groups='base.group_portal')

    def setUp(self):
        super().setUp()
        self.authenticate('safra_12pend_prueba', 'safra_12pend_prueba')

    def test_modulo_rf_y_cargador_desde_la_linea(self):
        res = self.make_jsonrpc_request('/cotizador/ajax/motor_extras',
                                        {'motor': self.motor.code, 'system_id': self.enrollable.id})
        self.assertTrue(res['interruptor'])
        self.assertTrue(res['cargador'])

    def test_controles_no_salen_del_maestro(self):
        """Sin referencia de controles para el motor, el «U_Controles
        compatibles» del maestro ya no se ofrece."""
        res = self.make_jsonrpc_request('/cotizador/ajax/motor_extras',
                                        {'motor': self.motor.code, 'system_id': self.enrollable.id})
        etiquetas = [c['label'] for c in res['controls']]
        self.assertNotIn('Control Maestro Prueba', etiquetas)
        # Con la línea del control en Referencias (columna Motores) sí sale.
        self.assertIn(self.ctl_mono._portal_label(), etiquetas)

    def test_control_sin_stock_en_gris(self):
        """Acta del 30-oct (Tubo, punto 8): el control sin existencias sigue
        en la lista, sin stock; «Sin control» siempre sirve."""
        self.ctl_mono.fabric_id.cant_min_stock = 1
        res = self.make_jsonrpc_request('/cotizador/ajax/motor_extras',
                                        {'motor': self.motor.code, 'system_id': self.enrollable.id})
        disponibles = {c['value']: c['available'] for c in res['controls']}
        self.assertEqual(disponibles[self.ctl_mono._valor_control()], 0)
        self.assertEqual(disponibles.get('0', 1), 1)
