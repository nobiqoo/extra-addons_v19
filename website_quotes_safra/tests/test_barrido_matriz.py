# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from odoo import fields, http
from odoo.tests import HttpCase, new_test_user, tagged

from .common import SafraCommon
from .test_ajustes_16 import Ajustes16Common


def _sin_codigo(issues):
    return [i['message'].rsplit(' [', 1)[0] for i in issues]


@tagged('post_install', '-at_install', 'safra')
class TestReglasBarrido(SafraCommon):
    """Barrido de la matriz (03-nov): Posición del mando obligatoria sin
    Mismo cabezal (fila 77) y datos de despacho (filas 184-188)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().search(
            [('key', 'in', ('website_quotes_safra.ajuste_barrido_matriz',
                            'website_quotes_safra.ajuste_tela_cenefa_en_tela',
                            'website_quotes_safra.ajuste_orden_resumen'))]).unlink()
        cls.env['safra.validation.rule']._ajuste_barrido_matriz()
        cls.env['safra.validation.rule']._ajuste_tela_cenefa_en_tela()
        cls.env['safra.validation.rule']._ajuste_orden_resumen()
        cls.env['safra.system.field'].create({
            'system_id': cls.enrollable.id, 'field_id': cls._campo('mando_position').id,
            'sequence': 500})
        cls.colombia = cls.env.ref('base.co')
        cls.ciudad = cls.env['res.city'].create({'name': 'Ciudad Prueba', 'country_id': cls.colombia.id})

    def test_reglas_creadas_una_vez(self):
        Rule = self.env['safra.validation.rule']
        reglas = Rule.search([('code', 'in', ('V_MANDO_OBLIGATORIO', 'V_DESPACHO_DATOS',
                                              'V_CENEFA_EN_TELA_TELA'))])
        self.assertEqual(sorted(reglas.mapped('momento')), ['linea', 'linea', 'pedido'])
        self.assertTrue(all(reglas.mapped('del_modulo')))
        Rule._ajuste_barrido_matriz()
        self.assertEqual(Rule.search_count([('code', '=', 'V_MANDO_OBLIGATORIO')]), 1)

    # --- Fila 77 ----------------------------------------------------------

    def test_mando_obligatorio_sin_mismo_cabezal(self):
        avisos = lambda **v: _sin_codigo(self.mensajes(
            [self.linea(**v)], 'V_MANDO_OBLIGATORIO', cross=False))
        self.assertEqual(avisos(mando_position=''), ['E13095: Seleccione la Posición del mando.'])
        self.assertFalse(avisos(mando_position='derecha'))
        # Con Mismo cabezal el mando lo define la secuencia.
        self.assertFalse(avisos(mando_position='', same_header=True, sequence_name='S1'))

    def test_mando_sin_el_campo_no_se_revisa(self):
        self.assertFalse(self.mensajes([self.linea_panel(4, mando_position='')],
                                       'V_MANDO_OBLIGATORIO', cross=False))

    # --- Filas 184-188 ----------------------------------------------------

    def despacho(self, **pedido):
        base = {'pide_despacho': True, 'recoge_fabrica': False, 'despacho_country_id': False,
                'despacho_city_id': False, 'despacho_direccion': '', 'despacho_destinatario': '',
                'despacho_fecha': False}
        base.update(pedido)
        issues = self.Line._validate_order([self.linea(mando_position='derecha')], cross=True,
                                           pedido=base)
        return _sin_codigo([i for i in issues if i['code'] == 'V_DESPACHO_DATOS'])

    def test_despacho_pide_pais_ciudad_y_destinatario(self):
        self.assertEqual(self.despacho(), [
            'E13095: Complete los datos de despacho: país, ciudad y nombre del destinatario '
            '(o marque «Recoge en fábrica»).'])
        completo = {'despacho_country_id': self.colombia.id, 'despacho_city_id': self.ciudad.id,
                    'despacho_destinatario': 'Ana Pérez'}
        self.assertFalse(self.despacho(**completo))
        self.assertTrue(self.despacho(**dict(completo, despacho_destinatario='')))

    def test_despacho_es_del_pedido(self):
        # Con una sola persiana el mensaje sale como del pedido, no de la persiana 1.
        issues = self.Line._validate_order(
            [self.linea(mando_position='derecha')], cross=True,
            pedido={'pide_despacho': True, 'recoge_fabrica': False, 'despacho_country_id': False,
                    'despacho_city_id': False, 'despacho_direccion': '', 'despacho_destinatario': '',
                    'despacho_fecha': False})
        self.assertEqual([i['line'] for i in issues if i['code'] == 'V_DESPACHO_DATOS'], [0])

    def test_recoge_en_fabrica_no_pide_despacho(self):
        self.assertFalse(self.despacho(recoge_fabrica=True))

    def test_cotizacion_de_antes_no_se_revisa(self):
        self.assertFalse(self.despacho(pide_despacho=False))
        quote = self.env['safra.quote'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Cliente Prueba'}).id,
            'line_ids': [(0, 0, self.linea(mando_position='derecha'))]})
        self.assertFalse(quote._datos_pedido()['pide_despacho'])

    # --- Revisión 05-nov: hoy en Colombia (calendario del despacho) -------

    def test_hoy_es_de_colombia(self):
        # 4-nov 9 p. m. en Colombia ya es 5-nov 2 a. m. en el servidor (UTC).
        self.env.company.partner_id.tz = False
        noche = datetime(2026, 11, 5, 2, 0, 0)
        self.assertEqual(self.env['safra.quote']._hoy_colombia(noche), date(2026, 11, 4))
        self.assertEqual(self.env['safra.quote']._hoy_colombia(datetime(2026, 11, 5, 5, 0, 0)),
                         date(2026, 11, 5))

    # --- Fila 50: telas no compatibles por línea --------------------------

    def perfiles(self):
        """Referencia de perfiles como la del 28-oct: el redondo no sirve con
        la tela gruesa (se atasca); el cuadrado sirve con todas."""
        Option = self.env['safra.product.option']
        cat = Option.create({'name': 'Perfil barrido', 'type': 'ref_categoria'})
        self.env['safra.field'].create({
            'code': 'zt_perfil_b', 'name': 'Perfil barrido', 'field_type': 'ref_categoria',
            'ref_category_id': cat.id, 'section_id': self._campo('perfil').section_id.id})
        self.env['safra.system.field'].create({
            'system_id': self.enrollable.id,
            'field_id': self.env['safra.field'].search([('code', '=', 'zt_perfil_b')]).id,
            'sequence': 900})
        ref = self.env['safra.fabric'].create({'code': 'ZT-PB', 'name': 'Perfiles B',
                                               'category_id': cat.id})
        Color = self.env['safra.fabric.color']
        cuadrado = Color.create({'fabric_id': ref.id, 'code': 'ZTPB1', 'name': 'Perfil cuadrado'})
        redondo = Color.create({'fabric_id': ref.id, 'code': 'ZTPB2', 'name': 'Perfil redondo',
                                'tela_excluida_ids': [(6, 0, self.tela_pesada.ids)]})
        return ref, cuadrado, redondo

    def codigos_perfil(self, perfil, tela, color):
        return self.codigos([self.linea(fabric_id=tela.id, color_id=color.id,
                                        mando_position='derecha',
                                        attribute_values={'zt_perfil_b': perfil})], cross=False)

    def test_perfil_no_compatible_con_una_tela(self):
        ref, cuadrado, redondo = self.perfiles()
        self.assertFalse(redondo._sirve_con_telas(self.tela_pesada))
        self.assertTrue(redondo._sirve_con_telas(self.tela))
        self.assertTrue(cuadrado._sirve_con_telas(self.tela_pesada))
        # El redondo no sale con la tela gruesa; con las demás, sí.
        self.assertIn('V_OPCION_TELA', self.codigos_perfil('ZTPB2', self.tela_pesada, self.pesada))
        self.assertNotIn('V_OPCION_TELA', self.codigos_perfil('ZTPB2', self.tela, self.blanco))
        # Sin telas no compatibles, el perfil sirve con todas.
        self.assertNotIn('V_OPCION_TELA', self.codigos_perfil('ZTPB1', self.tela_pesada, self.pesada))

    def test_perfil_con_dos_colores(self):
        ref, cuadrado, redondo = self.perfiles()
        # Otra línea con la misma etiqueta (otro color del perfil redondo).
        otro = self.env['safra.fabric.color'].create({
            'fabric_id': ref.id, 'code': 'ZTPB3', 'name': 'Perfil redondo'})
        # Comparte la restricción del otro color: basta marcarla en una línea.
        self.assertFalse(otro._sirve_con_telas(self.tela_pesada))
        self.assertTrue(otro._sirve_con_telas(self.tela))
        self.assertTrue(cuadrado._sirve_con_telas(self.tela_pesada))

    def test_perfil_con_dos_telas(self):
        ref, cuadrado, redondo = self.perfiles()
        # Basta una tela no compatible en la persiana.
        self.assertFalse(redondo._sirve_con_telas(self.tela | self.tela_pesada))

    def test_restriccion_de_la_referencia_se_suma(self):
        ref, cuadrado, redondo = self.perfiles()
        ref.tela_ids = self.tela
        self.assertFalse(cuadrado._sirve_con_telas(self.tela_pesada))
        self.assertTrue(cuadrado._sirve_con_telas(self.tela))
        self.assertIn('V_OPCION_TELA', self.codigos_perfil('ZTPB1', self.tela_pesada, self.pesada))


    # --- Fila 89: tela de la cenefa en tela -------------------------------

    def campo_cenefa_en_tela(self):
        return self.env['safra.field'].with_context(active_test=False).search(
            [('code', '=', 'cenefa_tela_panel')])

    def test_campos_con_telas_elegidas(self):
        Field = self.env['safra.field'].with_context(active_test=False)
        nuevo = self.campo_cenefa_en_tela()
        self.assertEqual(len(nuevo), 1)
        self.assertEqual(nuevo.opciones_telas, 'color')
        # Se activa con Cenefa en tela, no con «¿Cenefa forrada?».
        self.assertEqual(nuevo.depends_field_id.code, 'cenefa_panel')
        self.assertIn('ref:CEN-TELA', nuevo.depends_value)
        self.assertEqual(Field.search([('code', '=', 'cenefa_tela')]).opciones_telas, 'color')
        self.assertEqual(Field.search([('code', '=', 'cabezal_tela')]).opciones_telas, 'referencia')
        # Va en los sistemas de varias telas que tienen «Tela de Cenefa».
        Mapping = self.env['safra.system.field'].with_context(active_test=False)
        con_tela = Mapping.search([('field_id.code', '=', 'cenefa_tela'),
                                   ('system_id.code', 'in', ['11', '54'])]).system_id
        self.assertEqual(Mapping.search([('field_id', '=', nuevo.id)]).system_id, con_tela)

    def test_ajuste_conserva_lo_configurado(self):
        Field = self.env['safra.field'].with_context(active_test=False)
        cabezal = Field.search([('code', '=', 'cabezal_tela')])
        cabezal.opciones_telas = 'color'
        self.env['ir.config_parameter'].sudo().set_param(
            'website_quotes_safra.ajuste_tela_cenefa_en_tela', '')
        self.env['safra.validation.rule']._ajuste_tela_cenefa_en_tela()
        self.assertEqual(cabezal.opciones_telas, 'color')
        self.assertEqual(len(self.campo_cenefa_en_tela()), 1)

    def test_ajuste_devuelve_la_lista_al_campo_existente(self):
        # Si la columna se perdió (actualizar sin este código), el campo queda
        # sin «Opciones: telas elegidas»: el ajuste se la vuelve a poner.
        self.campo_cenefa_en_tela().opciones_telas = False
        self.env['ir.config_parameter'].sudo().set_param(
            'website_quotes_safra.ajuste_tela_cenefa_en_tela', '')
        self.env['safra.validation.rule']._ajuste_tela_cenefa_en_tela()
        self.assertEqual(self.campo_cenefa_en_tela().opciones_telas, 'color')
        self.assertEqual(len(self.campo_cenefa_en_tela()), 1)

    def test_cenefa_en_tela_pide_la_tela(self):
        regla = self.env['safra.validation.rule'].search([('code', '=', 'V_CENEFA_EN_TELA_TELA')])
        self.assertEqual(regla.momento, 'linea')
        regla.system_ids |= self.panel
        self.env['safra.system.field'].create({
            'system_id': self.panel.id, 'field_id': self.campo_cenefa_en_tela().id, 'sequence': 900})

        def avisos(**attrs):
            return _sin_codigo(self.mensajes([self.linea_panel(4, attribute_values=attrs)],
                                             'V_CENEFA_EN_TELA_TELA', cross=False))
        self.assertEqual(avisos(cenefa_panel='I100002014'),
                         ['E13084: Seleccione la tela de la cenefa en tela.'])
        self.assertFalse(avisos(cenefa_panel='I100002014', cenefa_tela_panel='Tela Prueba Blanco Prueba'))
        # Con otra cenefa (p. ej. la metálica) no se pide.
        self.assertFalse(avisos(cenefa_panel='2815'))

    # --- Fila 124 ---------------------------------------------------------

    def resumen(self, **vals):
        partner = self.env['res.partner'].create({'name': 'Cliente Resumen'})
        quote = self.env['safra.quote'].create({
            'partner_id': partner.id,
            'line_ids': [(0, 0, self.linea(aligned=True, same_header=True, sequence_name='Ventanal',
                                           **vals))]})
        return quote.line_ids._resumen_portal()

    def test_resumen_como_el_portal_de_safra(self):
        res = self.resumen()
        self.assertEqual(res['nombre'], 'Persiana PRUEBA ENROLLABLE Tela Prueba Blanco Prueba')
        self.assertEqual((res['ancho'], res['alto'], res['cantidad']), (1.5, 1.8, 1))
        # En el formulario Posición del mando va de último y Localización
        # antes de Alineado; en el resumen, como Safra. Lo que Safra no
        # muestra va después, en el orden del formulario.
        self.assertEqual([e for e, _v in res['caracteristicas']],
                         ['Posición del mando', 'Alineado', 'Localización',
                          'Mismo cabezal o Soporte intermedio', 'Nombre secuencia'])
        # La tela, las medidas y la cantidad van en el nombre, no se repiten.
        valores = [v for _e, v in res['caracteristicas']]
        self.assertNotIn('Tela Prueba', valores)
        self.assertNotIn('1.5', valores)
        self.assertEqual(res['mecanismo'], 'Tubo: R8 - Mecanismo: R8SL - Cabezal: No aplica')

    def test_resumen_oculta_lo_que_la_tela_no_permite(self):
        # Como el formulario: Atravesar Tela solo con telas atravesables.
        self.env['safra.system.field'].create({
            'system_id': self.enrollable.id, 'field_id': self._campo('atravesar_tela').id, 'sequence': 600})
        self.assertNotIn('Atravesar Tela', dict(self.resumen()['caracteristicas']))
        self.tela.pierceable_type = 'si_cliente'
        self.assertEqual(dict(self.resumen()['caracteristicas'])['Atravesar Tela'], 'Predeterminado')

    def test_orden_del_resumen_se_cambia_en_el_campo(self):
        self._campo('location').resumen_sequence = 1
        self._campo('sequence_name').resumen_sequence = 2
        self.assertEqual([e for e, _v in self.resumen()['caracteristicas']][:3],
                         ['Localización', 'Nombre secuencia', 'Posición del mando'])

    def test_ajuste_del_orden_conserva_lo_configurado(self):
        self._campo('location').resumen_sequence = 5
        self._campo('aligned').resumen_sequence = 0
        self.env['ir.config_parameter'].sudo().set_param('website_quotes_safra.ajuste_orden_resumen', '')
        self.env['safra.validation.rule']._ajuste_orden_resumen()
        self.assertEqual(self._campo('location').resumen_sequence, 5)
        self.assertEqual(self._campo('aligned').resumen_sequence, 40)
        self.assertEqual(self._campo('perfil').resumen_sequence, 10)


@tagged('post_install', '-at_install', 'safra')
class TestDespachoPortal(HttpCase, Ajustes16Common):
    """Datos de despacho en el portal (filas 184-188) y la cotización vista
    desde la mesa de ayuda (fila 191)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().search(
            [('key', 'in', ('website_quotes_safra.ajuste_barrido_matriz',
                            'website_quotes_safra.ajuste_tela_cenefa_en_tela',
                            'website_quotes_safra.ajuste_orden_resumen'))]).unlink()
        cls.env['safra.validation.rule']._ajuste_barrido_matriz()
        cls.env['safra.validation.rule']._ajuste_tela_cenefa_en_tela()
        cls.env['safra.validation.rule']._ajuste_orden_resumen()
        cls.usuario = new_test_user(cls.env, login='safra_desp', groups='base.group_portal')
        cls.colombia = cls.env.ref('base.co')
        cls.ciudad = cls.env['res.city'].create({'name': 'Ciudad Prueba', 'country_id': cls.colombia.id})
        cls.otra = cls.env['res.city'].create({'name': 'Ciudad Lejana',
                                               'country_id': cls.env.ref('base.pe').id})

    def setUp(self):
        super().setUp()
        self.authenticate('safra_desp', 'safra_desp')

    def formulario(self, **extra):
        form = {'system_id_0': self.enrollable.id, 'fabric_id_0': self.tela.id,
                'color_id_0': self.blanco.id, 'width_0': '1.5', 'height_0': '1.8',
                'quantity_0': '1', 'location_0': 'Sala', 'despacho_bloque': '1'}
        form.update(extra)
        return form

    def dentro_de_15(self):
        return fields.Date.to_string(self.env['safra.quote']._hoy_colombia() + timedelta(days=15))

    def test_calendario_desde_hoy(self):
        hoy = fields.Date.to_string(self.env['safra.quote']._hoy_colombia())
        self.assertIn('min="%s"' % hoy, self.url_open('/cotizador').text)

    def post(self, ruta, data=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(ruta, data=data, allow_redirects=False)

    def cotizaciones(self):
        return self.env['safra.quote'].search([('partner_id', '=', self.usuario.partner_id.id)])

    def test_sin_datos_no_finaliza(self):
        res = self.post('/cotizador/submit', self.formulario())
        self.assertEqual(res.status_code, 200)
        self.assertIn('Complete los datos de despacho', res.text)
        self.assertFalse(self.cotizaciones())

    def test_guarda_los_datos_de_despacho(self):
        res = self.post('/cotizador/submit', self.formulario(
            despacho_country_id=str(self.colombia.id), despacho_city_id=str(self.ciudad.id),
            despacho_direccion='Calle 1 # 2-3', despacho_destinatario='Ana Pérez',
            despacho_fecha=self.dentro_de_15()))
        self.assertEqual(res.status_code, 303)
        quote = self.cotizaciones()
        self.assertEqual((quote.despacho_country_id, quote.despacho_city_id), (self.colombia, self.ciudad))
        self.assertEqual((quote.despacho_direccion, quote.despacho_destinatario),
                         ('Calle 1 # 2-3', 'Ana Pérez'))
        self.assertEqual(str(quote.despacho_fecha), self.dentro_de_15())
        self.assertTrue(quote.despacho_registrado)
        self.assertIn('Destinatario: Ana Pérez', self.url_open('/mis-cotizaciones/%d' % quote.id).text)

    def test_recoge_en_fabrica_solo_guarda_la_fecha(self):
        res = self.post('/cotizador/submit', self.formulario(
            recoge_fabrica='1', despacho_country_id=str(self.colombia.id),
            despacho_destinatario='Nadie', despacho_fecha=self.dentro_de_15()))
        self.assertEqual(res.status_code, 303)
        quote = self.cotizaciones()
        self.assertTrue(quote.recoge_fabrica)
        self.assertFalse(quote.despacho_country_id or quote.despacho_destinatario)
        self.assertEqual(str(quote.despacho_fecha), self.dentro_de_15())

    def test_ciudad_de_otro_pais_no_se_guarda(self):
        res = self.post('/cotizador/submit', self.formulario(
            despacho_country_id=str(self.colombia.id), despacho_city_id=str(self.otra.id),
            despacho_destinatario='Ana Pérez'))
        # Sin ciudad válida la regla no deja finalizar.
        self.assertEqual(res.status_code, 200)
        self.assertFalse(self.cotizaciones())

    def test_ciudades_por_pais(self):
        ciudades = self.make_jsonrpc_request('/cotizador/ajax/ciudades', {'country_id': self.colombia.id})
        nombres = [c['name'] for c in ciudades]
        self.assertIn('Ciudad Prueba', nombres)
        self.assertNotIn('Ciudad Lejana', nombres)

    def test_config_dice_que_lista_las_telas(self):
        nuevo = self.env['safra.field'].search([('code', '=', 'cenefa_tela_panel')])
        self.env['safra.system.field'].create({
            'system_id': self.enrollable.id, 'field_id': nuevo.id, 'sequence': 900})
        config = self.make_jsonrpc_request('/cotizador/ajax/config', {'system_id': self.enrollable.id})
        campos = {f['code']: f for f in config['fields']}
        self.assertEqual(campos['cenefa_tela_panel']['telas_elegidas'], 'color')
        otros = [f['telas_elegidas'] for c, f in campos.items() if c != 'cenefa_tela_panel']
        self.assertTrue(otros)
        self.assertFalse(any(otros))

    def test_resumen_en_el_detalle_y_en_el_formulario(self):
        self.post('/cotizador/submit', self.formulario(recoge_fabrica='1'))
        quote = self.cotizaciones()
        detalle = self.url_open('/mis-cotizaciones/%d' % quote.id).text
        for texto in ('>Características</th>', 'Persiana PRUEBA ENROLLABLE Tela Prueba Blanco Prueba',
                      'Dimensiones:', '1.5 mts', '1.8 mts', '1 und', 'Opciones de la línea 1'):
            self.assertIn(texto, detalle)
        # El formulario recibe el orden del resumen de cada campo.
        config = self.make_jsonrpc_request('/cotizador/ajax/config', {'system_id': self.enrollable.id})
        campos = {f['code']: f['resumen'] for f in config['fields']}
        self.assertEqual(campos['aligned'], 40)
        self.assertEqual(campos['same_header'], 0)

    # --- Fila 191 ---------------------------------------------------------

    def test_mesa_de_ayuda_solo_consulta(self):
        quote = self.env['safra.quote'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Otro cliente'}).id,
            'line_ids': [(0, 0, self.linea())]})
        ticket = self.env['helpdesk.ticket'].create({'name': 'Verificación', 'safra_quote_id': quote.id})
        accion = ticket.action_safra_ver_portal()
        self.assertEqual(accion['url'], '/mis-cotizaciones/%d' % quote.id)
        # El cliente del portal no la ve (no es suya).
        self.assertEqual(self.url_open(accion['url']).status_code, 404)
        new_test_user(self.env, login='safra_mesa', groups='base.group_user,helpdesk.group_helpdesk_user')
        self.authenticate('safra_mesa', 'safra_mesa')
        res = self.url_open(accion['url'])
        self.assertEqual(res.status_code, 200)
        self.assertIn('Vista de consulta desde la mesa de ayuda', res.text)
        self.assertNotIn('Editar cotización', res.text)
        self.assertNotIn('Duplicar pedido', res.text)
        self.assertNotIn('Opciones de la línea', res.text)
        # Las acciones siguen cerradas aunque se fuerce la ruta.
        self.post('/mis-cotizaciones/%d/eliminar' % quote.id)
        self.assertTrue(quote.exists())
