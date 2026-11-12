# -*- coding: utf-8 -*-
import base64
import io

from PIL import Image

from odoo import http
from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import SafraCommon


def _png(ancho, alto):
    buf = io.BytesIO()
    Image.new('RGB', (ancho, alto), 'white').save(buf, 'PNG')
    return base64.b64encode(buf.getvalue())


class Ajustes1415Common(SafraCommon):
    """Ajustes del Sprint 1.4 (reunión 20-oct) y 1.5 (reunión 22-oct). Las
    fórmulas se ponen aquí con las iniciales: en la base pueden estar
    editadas por el funcional."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Field = cls.env['safra.field']
        Option = cls.env['safra.field.option']

        def opcion(code, valor, nombre):
            field = cls._campo(code)
            return field.option_ids.filtered(lambda o: o.value == valor)[:1] or Option.create(
                {'field_id': field.id, 'value': valor, 'name': nombre})
        for (code, valor), (formula, aviso) in Field.AJUSTES_1415_AUTO.items():
            opcion(code, valor, 'Sí').write({'auto_formula': formula, 'aviso': aviso, 'formula': False})
        for (code, valor), formula in Field.AJUSTES_1415_FORMULA.items():
            opcion(code, valor, 'Cenefa Entera').write({'formula': formula, 'auto_formula': False})
        opcion('cenefa_dividida', '0', 'No')
        # Dependencias con las que se siembra el módulo (Safra las cambia por
        # las de sus referencias).
        tipo = cls._campo('cenefa_panel')
        cls._campo('cenefa_dividida').write({'depends_field_id': tipo.id, 'depends_value': Field._S14_CON})
        cls._campo('corte_cenefa').write({'depends_field_id': tipo.id, 'depends_value': Field._S14_TELA})

        cls.sistema = cls._sistema('ZT14', 'PRUEBA AJUSTES', [
            'width', 'height', 'quantity', 'location', 'fabric_id', 'color_id',
            'cenefa_panel', 'cenefa_dividida', 'corte_cenefa', 'riel_tipo',
            'traslape_centro', 'cover_light_profile', 'coverlight_felpa'], (0.30, 8.00, 0.30, 4.00))
        cls.tela.system_ids |= cls.sistema
        cls.cenefa_pvc = cls._referencia('cenefa_panel', 'ZT-CEN', 'ZTCPVC', 'PVC 3 m', safra_u_ancho_max=3.0)
        cls.riel_3 = cls._referencia('riel_tipo', 'ZT-RIEL14', 'ZTR3', 'Riel 3 m', safra_u_ancho_max=3.0)

    @classmethod
    def _referencia(cls, campo, ref_code, code, etiqueta, ref=None, **producto):
        categoria = cls._campo(campo).ref_category_id
        ref = ref or cls.env['safra.fabric'].create(
            {'code': ref_code, 'name': 'Referencia %s' % ref_code, 'category_id': categoria.id})
        tmpl = cls.env['product.template'].create(dict(
            {'name': etiqueta, 'safra_code': code, 'safra_is_color': True}, **producto))
        return cls.env['safra.fabric.color'].create(
            {'fabric_id': ref.id, 'product_tmpl_id': tmpl.id, 'etiqueta': etiqueta})

    def linea_ajustes(self, ancho=1.5, alto=1.8, **attrs):
        return self.linea(system_id=self.sistema.id, width=ancho, height=alto, attribute_values=attrs)

    def formulas(self, vals):
        return self.Line.new(vals)._formulas_opciones()


@tagged('post_install', '-at_install', 'safra')
class TestAjustes1415(Ajustes1415Common):

    # --- Fila 88: cenefa dividida --------------------------------------

    def test_cenefa_dividida_por_el_rollo(self):
        """Sin ancho máximo de la cenefa manda el ancho del rollo (2,50 m)."""
        auto = self.formulas(self.linea_ajustes(2.8, cenefa_panel='2'))['auto']
        self.assertEqual(auto.get('cenefa_dividida'), '1')
        self.assertNotIn('cenefa_dividida', self.formulas(self.linea_ajustes(2.0, cenefa_panel='2'))['auto'])

    def test_cenefa_dividida_por_el_maximo_de_la_cenefa(self):
        """Con la cenefa de Referencias manda su U_AnchoMax (3 m)."""
        valor = 'ref-%d' % self.cenefa_pvc.id
        res = self.formulas(self.linea_ajustes(2.8, cenefa_panel=valor))
        self.assertNotIn('cenefa_dividida', res['auto'])
        res = self.formulas(self.linea_ajustes(3.2, cenefa_panel=valor))
        self.assertEqual(res['auto'].get('cenefa_dividida'), '1')
        self.assertIn('Recuerde que su cenefa va a ir dividida', ' '.join(res['avisos']['cenefa_dividida']))

    # --- Fila 91: cenefa añadida / entera ------------------------------

    def test_cenefa_anadida_por_encima_del_rollo(self):
        res = self.formulas(self.linea_ajustes(2.8, cenefa_panel='2'))
        self.assertEqual(res['auto'].get('corte_cenefa'), '1')
        self.assertNotIn('2', res['opciones']['corte_cenefa'])
        res = self.formulas(self.linea_ajustes(2.0, cenefa_panel='2'))
        self.assertNotIn('corte_cenefa', res['auto'])
        self.assertIn('2', res['opciones']['corte_cenefa'])

    def test_cenefa_entera_con_tela_que_la_permite(self):
        self.tela.permite_cenefa_entera = True
        res = self.formulas(self.linea_ajustes(2.8, cenefa_panel='2'))
        self.assertNotIn('corte_cenefa', res['auto'])
        self.assertIn('2', res['opciones']['corte_cenefa'])

    # --- Fila 102: riel dividido ---------------------------------------

    def test_riel_dividido_por_el_maximo_del_riel(self):
        valor = 'ref-%d' % self.riel_3.id
        self.assertNotIn('traslape_centro', self.formulas(self.linea_ajustes(2.8, riel_tipo=valor))['auto'])
        auto = self.formulas(self.linea_ajustes(3.2, riel_tipo=valor))['auto']
        self.assertEqual(auto.get('traslape_centro'), '2')

    def test_riel_dividido_en_cortinas_manual_y_motorizada(self):
        """Las cortinas no eligen riel: 5,80 m manual y 6,00 m con motor."""
        cortina = self.env['safra.system'].search([('code', '=', '49')], limit=1)
        if not cortina or 'traslape_centro' not in self.Line.new({'system_id': cortina.id})._system_field_codes():
            self.skipTest('La base no tiene la cortina 49 con Riel dividido')
        vals = dict(self.linea(system_id=cortina.id, width=5.9))
        self.assertEqual(self.formulas(vals)['auto'].get('traslape_centro'), '2')
        con_motor = dict(vals, attribute_values={'has_motor': '1'})
        self.assertNotIn('traslape_centro', self.formulas(con_motor)['auto'])
        con_motor['width'] = 6.1
        self.assertEqual(self.formulas(con_motor)['auto'].get('traslape_centro'), '2')

    def test_sistema_sin_el_campo_de_referencia(self):
        """La fórmula del riel usa ancho_max_riel_tipo: en un sistema sin
        ese campo vale 0 y no falla."""
        ctx = self.Line.new(self.linea())._ctx_formulas_opciones(self.env['safra.system.field'])
        self.assertEqual(ctx['ancho_max_riel_tipo'], 0.0)

    # --- E20042: la opción que se elige sola -----------------------------

    def test_e20042_opcion_que_se_elige_sola(self):
        sin_dividir = self.linea_ajustes(2.8, cenefa_panel='2', corte_cenefa='1', cenefa_dividida='0')
        mensajes = self.mensajes([sin_dividir], 'V_OPCION_AUTO', cross=False)
        self.assertEqual(len(mensajes), 1)
        self.assertIn('Recuerde que su cenefa va a ir dividida', mensajes[0]['message'])
        dividida = self.linea_ajustes(2.8, cenefa_panel='2', corte_cenefa='1', cenefa_dividida='1')
        self.assertNotIn('V_OPCION_AUTO', self.codigos([dividida], cross=False))

    def test_e20042_no_aplica_si_el_campo_no_se_ve(self):
        """Sin Tipo de cenefa, «¿Cenefa dividida?» no se muestra."""
        linea = self.linea_ajustes(2.8)
        self.assertNotIn('V_OPCION_AUTO', self.codigos([linea], cross=False))

    # --- Fila 94: dependencias por etiqueta -----------------------------

    def test_dependencia_por_etiqueta(self):
        Line = self.Line
        self.assertTrue(Line._depende_ok('ref-9', 'dos_laterales_5cm,eti:2 laterales', eti='2 Laterales'))
        self.assertTrue(Line._depende_ok('ref-9', 'eti:Sí', eti='si'))
        self.assertFalse(Line._depende_ok('ref-9', 'dos_laterales_5cm,eti:2 laterales', eti='3 Laterales'))
        self.assertTrue(Line._depende_ok('dos_laterales_5cm', 'dos_laterales_5cm,eti:2 laterales'))

    def test_felpa_con_cover_light_de_referencias(self):
        """Dos líneas del Cover Light comparten producto: la Felpa sale con
        la de 2 laterales (por su etiqueta)."""
        dos = self._referencia('cover_light_profile', 'ZT-CL', 'ZTCL', '2 Laterales')
        uno = self.env['safra.fabric.color'].create({
            'fabric_id': dos.fabric_id.id, 'product_tmpl_id': dos.product_tmpl_id.id, 'etiqueta': '1 Lateral'})
        maps = self.env['safra.system.field'].search([('system_id', '=', self.sistema.id)])
        felpa = maps.filtered(lambda m: m.field_id.code == 'coverlight_felpa')
        for linea, visible in ((dos, True), (uno, False)):
            line = self.Line.new(self.linea(system_id=self.sistema.id, cover_light_profile='ref-%d' % linea.id))
            self.assertEqual(line._campo_visible(felpa, maps), visible)

    def test_felpa_pasa_de_casilla_a_opcion(self):
        quote = self.env['safra.quote'].create({'partner_id': self.env['res.partner'].create({'name': 'Felpa'}).id})
        lineas = self.Line.create([dict(self.linea(), quote_id=quote.id, sequence=s) for s in (10, 20)])
        self.env.cr.execute("UPDATE safra_quote_line SET coverlight_felpa = %s WHERE id = %s", ('true', lineas[0].id))
        self.env.cr.execute("UPDATE safra_quote_line SET coverlight_felpa = %s WHERE id = %s", ('false', lineas[1].id))
        self.env['safra.field']._migrar_felpa()
        lineas.invalidate_recordset(['coverlight_felpa'])
        self.assertEqual(lineas.mapped('coverlight_felpa'), ['1', False])

    # --- Fila 118: corte por paños como aviso ----------------------------

    def test_panos_es_un_aviso(self):
        panos = self._campo('bajofalso').option_ids.filtered(lambda o: o.value == 'BN_PANOS')
        if not panos:
            self.skipTest('La base no tiene el Corte por paños')
        self.assertTrue(panos.solo_aviso)
        self.assertTrue(panos.aviso)

    # --- Siembra ---------------------------------------------------------

    def test_la_siembra_respeta_lo_editado(self):
        Param = self.env['ir.config_parameter'].sudo()
        opt = self._campo('cenefa_dividida').option_ids.filtered(lambda o: o.value == '1')
        opt.auto_formula = 'result = ancho > 4'
        segmentos = self.env['safra.field'].with_context(active_test=False).search_count([('code', '=', 'segmento_3')])
        Param.set_param('website_quotes_safra.ajustes_1415', '')
        self.env['safra.field']._apply_ajustes_1415()
        self.assertEqual(opt.auto_formula, 'result = ancho > 4')
        self.assertEqual(self.env['safra.field'].with_context(active_test=False).search_count(
            [('code', '=', 'segmento_3')]), segmentos)

    def test_segmento_3_creado_a_mano(self):
        """En la base de Safra el «segmento_3» se creó como número con el
        código por nombre: se conserva el campo y pasa a curva con su medida."""
        campo = self._campo('segmento_3')
        campo.option_ids.unlink()
        campo.write({'field_type': 'float', 'name': 'segmento_3'})
        self.env['ir.config_parameter'].sudo().set_param('website_quotes_safra.ajustes_1415', '')
        self.env['safra.field']._apply_ajustes_1415()
        self.assertEqual(self._campo('segmento_3'), campo)
        self.assertEqual((campo.field_type, campo.name), ('selection', 'Segmento 3'))
        self.assertEqual(campo.option_ids.mapped('value'), ['0.30', '0.50', 'mas'])

    def test_segmentos_en_los_sistemas_con_tipo_de_plano(self):
        con_plano = self.env['safra.system.field'].search(
            [('field_id.code', '=', 'tipoplano_cortina')]).mapped('system_id')
        for code in ('segmento_1_u', 'segmento_1_u_m', 'segmento_3', 'segmento_3_m'):
            con_campo = self.env['safra.system.field'].with_context(active_test=False).search(
                [('field_id.code', '=', code)]).mapped('system_id')
            self.assertFalse(con_plano - con_campo, code)

    # --- Filas 79 y 80: diseño de impresión ------------------------------

    def test_e20043_diseno_del_catalogo_por_resolucion(self):
        diseno = self.env['safra.design'].create({
            'code': 'ZTD1', 'name': 'Diseño prueba', 'image_print': _png(1000, 500)})
        vals = dict(design_print=True, custom_design=diseno.code)
        # 1000 px en 1 m = 25 DPI, por debajo del mínimo (40).
        grande = self.linea(width=1.0, height=0.5, **vals)
        self.assertIn('V_DISENO_RESOLUCION', self.codigos([grande], cross=False))
        chica = self.linea(width=0.5, height=0.25, **vals)
        self.assertNotIn('V_DISENO_RESOLUCION', self.codigos([chica], cross=False))
        # Mínimo del sistema.
        self.enrollable.diseno_dpi_minimo = 20
        self.assertNotIn('V_DISENO_RESOLUCION', self.codigos([grande], cross=False))
        # Diferencia de proporción permitida (imagen 2:1, persiana 1:1).
        self.enrollable.diseno_proporcion_max = 10
        cuadrada = self.linea(width=0.4, height=0.4, **vals)
        self.assertIn('V_DISENO_RESOLUCION', self.codigos([cuadrada], cross=False))

    def test_archivos_de_impresion_sin_reducir(self):
        """Odoo reduce las imágenes adjuntas a 1920 px: los archivos que van a
        impresión se guardan como se suben."""
        grande = _png(2400, 1200)
        diseno = self.env['safra.design'].create({'code': 'ZTD3', 'name': 'Original', 'image_print': grande})
        self.assertEqual(self.Line._medidas_imagen(base64.b64decode(diseno.image_print)), (2400, 1200))
        quote = self.env['safra.quote'].create({'partner_id': self.env['res.partner'].create({'name': 'Grande'}).id})
        line = self.Line.create(dict(self.linea(design_image=grande), quote_id=quote.id, sequence=10))
        line.design_final_file = grande
        for campo in ('design_image', 'design_final_file'):
            self.assertEqual(self.Line._medidas_imagen(base64.b64decode(line[campo])), (2400, 1200), campo)

    def test_diseno_sin_imagen_de_impresion_no_se_restringe(self):
        """La imagen del catálogo se reduce a 512 px: sin el archivo original
        no se mide."""
        diseno = self.env['safra.design'].create({'code': 'ZTD2', 'name': 'Sin original', 'image': _png(400, 200)})
        linea = self.linea(width=1.0, height=0.5, design_print=True, custom_design=diseno.code)
        self.assertNotIn('V_DISENO_RESOLUCION', self.codigos([linea], cross=False))

    def test_diseno_propio_no_se_restringe(self):
        linea = self.linea(width=3.0, height=2.0, design_print=True, custom_design='OTROS')
        self.assertNotIn('V_DISENO_RESOLUCION', self.codigos([linea], cross=False))

    def test_aprobar_diseno_exige_el_archivo_del_disenador(self):
        quote = self.env['safra.quote'].create({'partner_id': self.env['res.partner'].create({'name': 'Diseño'}).id})
        line = self.Line.create(dict(self.linea(design_print=True, custom_design='OTROS',
                                                design_image=_png(50, 50), design_filename='cliente.png'),
                                     quote_id=quote.id, sequence=10))
        line._create_design_ticket()
        ticket = line.design_ticket_id
        with self.assertRaises(UserError):
            ticket.action_safra_approve_design()
        self.assertFalse(line.design_approved)
        ticket.write({'safra_design_final_file': _png(60, 60), 'safra_design_final_filename': 'final.pdf'})
        ticket.action_safra_approve_design()
        self.assertTrue(line.design_approved)
        self.assertEqual(line.design_final_filename, 'final.pdf')


@tagged('post_install', '-at_install', 'safra')
class TestPortalAjustes1415(HttpCase, Ajustes1415Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usuario = new_test_user(cls.env, login='safra_portal_1415', groups='base.group_portal')

    def setUp(self):
        super().setUp()
        self.authenticate('safra_portal_1415', 'safra_portal_1415')

    def config(self, sistema):
        return self.make_jsonrpc_request('/cotizador/ajax/config', {'system_id': sistema.id})

    def campo(self, config, code):
        return next(f for f in config['fields'] if f['code'] == code)

    def test_lineas_con_el_mismo_producto(self):
        """Fila 94: cada línea del Cover Light se elige por la suya."""
        dos = self._referencia('cover_light_profile', 'ZT-CLP', 'ZTCLP', '2 Laterales')
        uno = self.env['safra.fabric.color'].create({
            'fabric_id': dos.fabric_id.id, 'product_tmpl_id': dos.product_tmpl_id.id, 'etiqueta': '1 Lateral'})
        opciones = self.campo(self.config(self.sistema), 'cover_light_profile')['options']
        por_eti = {o['eti']: o['value'] for o in opciones}
        self.assertEqual(por_eti['2 Laterales'], 'ref-%d' % dos.id)
        self.assertEqual(por_eti['1 Lateral'], 'ref-%d' % uno.id)

    def test_criterios_del_diseno_para_el_portal(self):
        self.enrollable.write({'diseno_dpi_minimo': 30, 'diseno_dpi_optimo': 60, 'diseno_proporcion_max': 15})
        self.assertEqual(self.config(self.enrollable)['diseno'],
                         {'dpi_min': 30, 'dpi_opt': 60, 'proporcion': 15})

    def test_opciones_con_formula_para_el_portal(self):
        config = self.config(self.sistema)
        self.assertTrue(self.campo(config, 'cenefa_dividida')['fml'])
        res = self.make_jsonrpc_request('/cotizador/ajax/opciones_formula', {
            'system_id': self.sistema.id,
            'campos': {'width': '2.8', 'height': '1.8', 'fabric_id': self.tela.id,
                       'color_id': self.blanco.id, 'cenefa_panel': '2'}})
        self.assertEqual(res['auto'].get('cenefa_dividida'), '1')
        self.assertTrue(res['avisos'].get('cenefa_dividida'))

    def test_comentarios_solo_para_el_grupo(self):
        """Fila 121: con grupo en Comentarios, ni el campo ni el cuadro de
        respaldo salen para los demás, y lo enviado no se guarda."""
        grupo = self.env['res.groups'].create({'name': 'Comentarios prueba'})
        comentarios = self._campo('description')
        comentarios.group_id = grupo
        self.env['safra.system.field'].create(
            {'system_id': self.enrollable.id, 'field_id': comentarios.id, 'sequence': 300})
        config = self.config(self.enrollable)
        self.assertNotIn('description', [f['code'] for f in config['fields']])
        self.assertFalse(config['comentarios_libres'])
        form = {'system_id_0': self.enrollable.id, 'fabric_id_0': self.tela.id, 'color_id_0': self.blanco.id,
                'width_0': '1.5', 'height_0': '1.8', 'quantity_0': '1', 'location_0': 'Sala',
                'description_0': 'No debe quedar', 'csrf_token': http.Request.csrf_token(self)}
        self.url_open('/cotizador/submit', data=form, allow_redirects=False)
        quote = self.env['safra.quote'].search([('partner_id', '=', self.usuario.partner_id.id)])
        self.assertTrue(quote)
        self.assertFalse(quote.line_ids.description)
        self.usuario.group_ids |= grupo
        self.assertIn('description', [f['code'] for f in self.config(self.enrollable)['fields']])

    def test_archivo_final_del_diseno_en_el_portal(self):
        quote = self.env['safra.quote'].create({'partner_id': self.usuario.partner_id.id})
        line = self.Line.create(dict(self.linea(design_print=True, custom_design='OTROS',
                                                design_image=_png(50, 50), design_filename='cliente.png'),
                                     quote_id=quote.id, sequence=10))
        line.write({'design_final_file': _png(60, 60), 'design_final_filename': 'final.png',
                    'design_approved': True})
        res = self.url_open('/mis-cotizaciones/%d/diseno/%d/final' % (quote.id, line.id))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, base64.b64decode(line.design_final_file))
        otro = self.env['safra.quote'].create({'partner_id': self.env['res.partner'].create({'name': 'Otro'}).id})
        line.quote_id = otro
        res = self.url_open('/mis-cotizaciones/%d/diseno/%d/final' % (otro.id, line.id))
        self.assertEqual(res.status_code, 404)
