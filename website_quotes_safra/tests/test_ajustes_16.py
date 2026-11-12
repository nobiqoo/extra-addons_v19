# -*- coding: utf-8 -*-
import io

import openpyxl

from odoo import http
from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged

from .test_sprint16 import Sprint16Common


class Ajustes16Common(Sprint16Common):
    """Ajustes del Sprint 1.6 (reunión 26-oct)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cat = cls.env['safra.product.option']._categoria_embalaje()
        ref = cls.env['safra.fabric'].create({'code': 'ZT-EMB', 'name': 'Embalajes Prueba',
                                              'category_id': cat.id})
        cls.caja = cls._color(ref, 'ZTCAJ', 'Caja sin logo')
        cls.bolsa = cls._color(ref, 'ZTBOL', 'Bolsa')

    def con_verificacion(self):
        quote = self.cotizacion(requiere_verificacion=True, verificacion_observaciones='Ajustar el tubo')
        quote._create_verification_ticket()
        quote._update_design_state()
        self.assertEqual(quote.state, 'pending_production')
        return quote


@tagged('post_install', '-at_install', 'safra')
class TestAjustes16(Ajustes16Common):

    def test_embalaje_tiene_su_categoria(self):
        cat = self.env['safra.product.option']._categoria_embalaje()
        self.assertEqual((cat.type, cat.name.lower()), ('ref_categoria', 'embalaje'))
        # Idempotente: no crea otra.
        self.env['safra.product.option']._setup_embalaje()
        self.assertEqual(self.env['safra.product.option']._categoria_embalaje(), cat)

    def test_nombre_de_la_linea_desde_el_producto(self):
        # La línea de embalaje toma el nombre del producto (antes quedaba
        # vacía y la etiqueta del backoffice salía en blanco).
        self.assertEqual(self.caja.name, 'Caja sin logo')
        self.assertEqual(self.caja.display_name, 'Caja sin logo')
        self.caja.product_tmpl_id.name = 'Caja kraft'
        self.assertEqual(self.caja.name, 'Caja kraft')

    def test_rechazo_de_verificacion(self):
        quote = self.con_verificacion()
        ticket = quote.verificacion_ticket_id
        with self.assertRaises(UserError):
            ticket.action_safra_reject_verification()
        ticket.safra_rechazo_motivo = 'El tubo R24 no soporta ese ancho'
        ticket.action_safra_reject_verification()
        self.assertEqual(quote.state, 'draft')
        self.assertTrue(quote.verificacion_rechazada)
        self.assertEqual(quote.verificacion_rechazo_motivo, 'El tubo R24 no soporta ese ancho')
        self.assertFalse(quote.verificacion_ticket_id)
        self.assertTrue(quote.editable_portal)
        # No vuelve sola a esperar a producción, no se confirma y el ticket
        # rechazado ya no se aprueba.
        quote._update_design_state()
        self.assertEqual(quote.state, 'draft')
        with self.assertRaises(UserError):
            quote.action_confirm()
        with self.assertRaises(UserError):
            ticket.action_safra_approve_production()

    def test_rechazar_requiere_el_grupo(self):
        ticket = self.con_verificacion().verificacion_ticket_id
        ticket.safra_rechazo_motivo = 'No'
        usuario = new_test_user(self.env, login='safra_sin_rechazo', groups='base.group_user,helpdesk.group_helpdesk_user')
        with self.assertRaises(UserError):
            ticket.with_user(usuario).action_safra_reject_verification()

    def test_duplicar_pedido(self):
        quote = self.cotizacion([self.linea(), self.linea(width=2.0)], es_exportacion=True,
                                orden_compra='OC-77', embalaje_ids=[(6, 0, self.caja.ids)])
        quote.action_confirm()
        usuario = new_test_user(self.env, login='safra_dup', groups='base.group_portal')
        copia = quote._duplicar_portal(usuario)
        self.assertNotEqual(copia, quote)
        self.assertNotEqual(copia.name, quote.name)
        self.assertEqual((copia.state, copia.partner_id, copia.user_id),
                         ('draft', usuario.partner_id, usuario))
        self.assertEqual(copia.line_ids.mapped('width'), [1.5, 2.0])
        self.assertEqual((copia.orden_compra, copia.embalaje_ids), ('OC-77', self.caja))
        self.assertFalse(copia.sale_order_id)
        # Sin el grupo Exportaciones la copia no queda de exportación.
        self.assertFalse(copia.es_exportacion)

    def test_eliminar_persiana(self):
        quote = self.cotizacion([self.linea(), self.linea(width=2.0), self.linea(width=2.2)])
        segunda = quote.line_ids.sorted('sequence')[1]
        self.assertEqual(quote._eliminar_linea_portal(segunda), [])
        self.assertEqual(quote.line_ids.sorted('sequence').mapped('width'), [1.5, 2.2])
        self.assertEqual(quote.line_ids.sorted('sequence').mapped('sequence'), [10, 20])

    def test_no_elimina_la_unica_persiana(self):
        quote = self.cotizacion()
        self.assertTrue(quote._eliminar_linea_portal(quote.line_ids))
        self.assertEqual(len(quote.line_ids), 1)

    def test_detalle_de_la_persiana(self):
        line = self.cotizacion().line_ids
        valores = dict(line._detalle_portal())
        self.assertIn('Tela Prueba', valores.values())
        self.assertIn('Blanco Prueba', valores.values())
        self.assertIn('Sala', valores.values())

    def test_orden_de_compra_en_el_pedido_de_venta(self):
        quote = self.cotizacion([self.linea(price_unit=1000)], orden_compra='OC-2026-15')
        quote.action_confirm()
        self.assertEqual(quote.sale_order_id.client_order_ref, 'OC-2026-15')
        sin_orden = self.cotizacion([self.linea(price_unit=1000)])
        sin_orden.action_confirm()
        self.assertEqual(sin_orden.sale_order_id.client_order_ref, sin_orden.name)

    def despachar(self, order):
        picking = order.picking_ids.filtered(lambda p: p.picking_type_code == 'outgoing')
        self.assertTrue(picking)
        for move in picking.move_ids:
            move.write({'quantity': move.product_uom_qty, 'picked': True})
        self.assertIs(picking.button_validate(), True)
        self.assertEqual(picking.state, 'done')
        return picking

    def pedido(self, **vals):
        quote = self.cotizacion([self.linea(price_unit=1000)], **vals)
        quote.action_confirm()
        return quote.sale_order_id

    def facturar_al_despachar(self, diario=True):
        """Factura al validar la entrega de stock_baseline: opción de la
        compañía y diario en el almacén."""
        self.env.company.create_invoices_from_picking = True
        if diario:
            almacen = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)])
            almacen.journal_id = self.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1)

    def test_facturar_al_despachar(self):
        self.facturar_al_despachar()
        order = self.pedido()
        picking = self.despachar(order)
        self.assertEqual(order.invoice_ids.mapped('state'), ['posted'])
        self.assertEqual(order.invoice_ids.journal_id, order.warehouse_id.journal_id)
        self.assertFalse(order.safra_facturacion_manual)
        self.assertIn('automatically created', picking.message_ids[0].body)

    def test_exportacion_y_proyectos_no_se_facturan_al_despachar(self):
        # Sin diario en el almacén: a estos pedidos tampoco se les pide.
        self.facturar_al_despachar(diario=False)
        for vals in ({'es_exportacion': True}, {'es_proyecto_especial': True}):
            order = self.pedido(**vals)
            self.assertTrue(order.safra_facturacion_manual)
            picking = self.despachar(order)
            self.assertFalse(order.invoice_ids)
            self.assertIn('no se factura al despachar', picking.message_ids[0].body)
            # Desde Ventas se facturan a mano como cualquier pedido.
            self.assertTrue(order._get_invoiceable_lines())

    def test_sin_la_opcion_no_factura(self):
        self.env.company.create_invoices_from_picking = False
        order = self.pedido()
        picking = self.despachar(order)
        self.assertFalse(order.invoice_ids)
        self.assertNotIn('no se factura al despachar', picking.message_ids[0].body)


@tagged('post_install', '-at_install', 'safra')
class TestPortalAjustes16(HttpCase, Ajustes16Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        empresa = cls.env['res.partner'].create({'name': 'Distribuidor Prueba', 'is_company': True})
        cls.usuario = new_test_user(cls.env, login='safra_a16', groups='base.group_portal')
        cls.colega = new_test_user(cls.env, login='safra_a16_colega', groups='base.group_portal')
        (cls.usuario.partner_id | cls.colega.partner_id).parent_id = empresa
        cls.cargo = cls.env['product.template'].create({
            'name': 'Tela con nota', 'safra_code': 'ZTNOTA', 'safra_is_color': True,
            'safra_u_observacion': 'Esta tela es bidireccional.'})
        cls.env['safra.fabric.color'].create({'fabric_id': cls.tela.id, 'product_tmpl_id': cls.cargo.id})

    def setUp(self):
        super().setUp()
        self.authenticate('safra_a16', 'safra_a16')

    def rpc(self, ruta, **params):
        return self.make_jsonrpc_request(ruta, params)

    def formulario(self, **extra):
        form = {'system_id_0': self.enrollable.id, 'fabric_id_0': self.tela.id,
                'color_id_0': self.blanco.id, 'width_0': '1.5', 'height_0': '1.8',
                'quantity_0': '1', 'location_0': 'Sala'}
        form.update(extra)
        return form

    def post(self, ruta, data=None, **kwargs):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(ruta, data=data, allow_redirects=False, **kwargs)

    def mis_cotizaciones(self, usuario=None):
        return self.env['safra.quote'].search(
            [('partner_id', '=', (usuario or self.usuario).partner_id.id)], order='id')

    def test_referencia_solo_trae_telas(self):
        controles = self.ctl_mono.fabric_id
        controles.system_ids = self.enrollable
        config = self.rpc('/cotizador/ajax/config', system_id=self.enrollable.id)
        nombres = [f['name'] for f in config['fabrics']]
        self.assertIn('Tela Prueba', nombres)
        self.assertNotIn(controles.name, nombres)

    def test_plantilla_del_cargue_en_todos_los_sistemas(self):
        sistemas = self.env['safra.system'].search([
            ('active', '=', True), ('product_tmpl_id.safra_is_system', '=', True)])
        self.assertTrue(sistemas)
        for sistema in sistemas.filtered(lambda s: s._visible_for_user(self.usuario)):
            res = self.url_open('/cotizador/cargue/plantilla?system_id=%d' % sistema.id)
            self.assertEqual(res.status_code, 200, sistema.name)
            hoja = openpyxl.load_workbook(io.BytesIO(res.content))['Persianas']
            self.assertEqual(hoja['A2'].value, 'system_id', sistema.name)
            self.assertEqual(hoja['A3'].value, sistema.name)

    def test_observacion_del_color(self):
        colores = {c['code']: c for c in self.rpc('/cotizador/ajax/colores', fabric_id=self.tela.id)}
        self.assertEqual(colores['ZTNOTA']['obs'], 'Esta tela es bidireccional.')
        self.assertEqual(colores['ZTBLA']['obs'], '')

    def test_embalaje_y_orden_de_compra(self):
        pagina = self.url_open('/cotizador')
        self.assertIn('Caja sin logo', pagina.text)
        self.assertIn('name="orden_compra"', pagina.text)
        # Un id que no es de Embalaje no se guarda.
        data = self.formulario(orden_compra='  OC-555 ')
        data = list(data.items()) + [('embalaje', str(self.caja.id)), ('embalaje', str(self.blanco.id))]
        res = self.url_open('/cotizador/submit', allow_redirects=False,
                            data=data + [('csrf_token', http.Request.csrf_token(self))])
        self.assertEqual(res.status_code, 303)
        quote = self.mis_cotizaciones()
        self.assertEqual((quote.orden_compra, quote.embalaje_ids), ('OC-555', self.caja))

    def test_proyectos_especiales_solo_con_su_grupo(self):
        self.post('/cotizador/submit', self.formulario(es_proyecto_especial='1'))
        self.assertFalse(self.mis_cotizaciones().es_proyecto_especial)
        self.usuario.group_ids |= self.env.ref('website_quotes_safra.group_safra_proyectos_especiales')
        self.assertIn('es_proyecto_especial', self.url_open('/cotizador').text)
        self.post('/cotizador/submit', self.formulario(es_proyecto_especial='1'))
        self.assertTrue(self.mis_cotizaciones()[-1].es_proyecto_especial)

    def test_resumen_con_acciones_por_persiana(self):
        self.post('/cotizador/submit', dict(self.formulario(), **{
            'system_id_1': self.enrollable.id, 'fabric_id_1': self.tela.id, 'color_id_1': self.gris.id,
            'width_1': '2.0', 'height_1': '1.8', 'quantity_1': '1', 'location_1': 'Alcoba'}))
        quote = self.mis_cotizaciones()
        self.assertEqual(len(quote.line_ids), 2)
        detalle = self.url_open('/mis-cotizaciones/%d' % quote.id).text
        self.assertIn('Tela Prueba', detalle)
        self.assertIn('/cotizador?editar=%d&amp;linea=2' % quote.id, detalle)
        self.assertIn('/cotizador?editar=%d&amp;duplicar=1' % quote.id, detalle)
        # «Editar» abre esa persiana; «Duplicar» agrega la copia en el formulario.
        self.assertIn('"linea": 2', self.url_open('/cotizador?editar=%d&linea=2' % quote.id).text)
        self.assertIn('"duplicar": 1', self.url_open('/cotizador?editar=%d&duplicar=1' % quote.id).text)
        primera = quote.line_ids.sorted('sequence')[0]
        self.post('/mis-cotizaciones/%d/linea/%d/eliminar' % (quote.id, primera.id))
        self.assertEqual(quote.line_ids.mapped('location'), ['Alcoba'])
        self.assertEqual(quote.line_ids.mapped('sequence'), [10])

    def test_duplicar_y_eliminar_el_pedido(self):
        self.post('/cotizador/submit', self.formulario())
        quote = self.mis_cotizaciones()
        quote.state = 'confirmed'
        res = self.post('/mis-cotizaciones/%d/duplicar' % quote.id)
        self.assertEqual(res.status_code, 303)
        copia = self.mis_cotizaciones() - quote
        self.assertEqual(copia.state, 'draft')
        # La confirmada no se elimina; la copia en Borrador sí.
        self.assertEqual(self.post('/mis-cotizaciones/%d/eliminar' % quote.id).status_code, 404)
        self.post('/mis-cotizaciones/%d/eliminar' % copia.id)
        self.assertFalse(copia.exists())

    def test_administrador_ve_los_pedidos_de_su_empresa(self):
        colega = self.cotizacion(partner_id=self.colega.partner_id.id, user_id=self.colega.id)
        self.assertEqual(self.url_open('/mis-cotizaciones/%d' % colega.id).status_code, 404)
        self.assertNotIn(colega.name, self.url_open('/mis-cotizaciones').text)
        self.usuario.group_ids |= self.env.ref('website_quotes_safra.group_safra_portal_admin')
        lista = self.url_open('/mis-cotizaciones').text
        self.assertIn(colega.name, lista)
        self.assertIn('Creada por', lista)
        self.assertEqual(self.url_open('/mis-cotizaciones/%d' % colega.id).status_code, 200)
        self.assertEqual(self.url_open('/cotizador?editar=%d' % colega.id, allow_redirects=False).status_code, 200)

    def test_corregir_tras_el_rechazo(self):
        self.usuario.group_ids |= self.env.ref('website_quotes_safra.group_safra_verificacion')
        # Reunión 09-nov (fila 74): sin aceptar que se evalúa sin garantía no se envía.
        res = self.post('/cotizador/submit', self.formulario(
            width_0='3.5', requiere_verificacion='1', verificacion_observaciones='Ajustar el tubo'))
        self.assertIn('acepte que el pedido se evalúa sin garantía', res.text)
        self.assertFalse(self.mis_cotizaciones())
        self.post('/cotizador/submit', self.formulario(
            width_0='3.5', requiere_verificacion='1', verificacion_observaciones='Ajustar el tubo',
            acepta_sin_garantia='1'))
        quote = self.mis_cotizaciones()
        self.assertTrue(quote.verificacion_acepta_sin_garantia)
        anterior = quote.verificacion_ticket_id
        anterior.safra_rechazo_motivo = 'Cambie el ancho'
        anterior.action_safra_reject_verification()
        self.assertIn('Cambie el ancho', self.url_open('/mis-cotizaciones/%d' % quote.id).text)
        # Lo corrige un usuario sin el grupo: la verificación se conserva.
        self.usuario.group_ids -= self.env.ref('website_quotes_safra.group_safra_verificacion')
        res = self.post('/cotizador/submit', dict(self.formulario(width_0='3.5'), quote_id=str(quote.id)))
        self.assertEqual(res.status_code, 303)
        self.assertTrue(quote.requiere_verificacion)
        self.assertFalse(quote.verificacion_rechazada)
        self.assertEqual(quote.state, 'pending_production')
        self.assertTrue(quote.verificacion_ticket_id)
        self.assertNotEqual(quote.verificacion_ticket_id, anterior)
