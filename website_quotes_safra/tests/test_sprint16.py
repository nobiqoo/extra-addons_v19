# -*- coding: utf-8 -*-
import io

import openpyxl

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.tests import HttpCase, new_test_user, tagged

from .common import SafraCommon


class Sprint16Common(SafraCommon):
    """Sprint 1.6: validaciones a nivel de pedido (Safra Express,
    exportación, verificación de fabricación) y parametrización."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Param = cls.env['ir.config_parameter'].sudo()
        Param.set_param('safra.express_pct', '15')
        Param.set_param('safra.express_max_unidades', '10')

    def linea(self, **extra):
        vals = {'system_id': self.enrollable.id, 'fabric_id': self.tela.id,
                'color_id': self.blanco.id, 'width': 1.5, 'height': 1.8,
                'quantity': 1, 'location': 'Sala'}
        vals.update(extra)
        return vals

    def cotizacion(self, lineas=None, **vals):
        partner = self.env['res.partner'].create({'name': 'Cliente Sprint 16'})
        quote = self.env['safra.quote'].create(dict({'partner_id': partner.id}, **vals))
        for n, linea in enumerate(lineas or [self.linea()], start=1):
            self.Line.create(dict(linea, quote_id=quote.id, sequence=n * 10))
        return quote


@tagged('post_install', '-at_install', 'safra')
class TestSprint16Pedido(Sprint16Common):

    def codigos(self, issues, severidad=None):
        return [i['code'] for i in issues if severidad is None or i['severity'] == severidad]

    def test_express_hasta_diez_unidades(self):
        diez = [self.linea(quantity=4), self.linea(quantity=6)]
        issues = self.Line._validate_order(diez, pedido={'safra_express': True})
        self.assertNotIn('V_EXPRESS_CANTIDAD', self.codigos(issues))
        once = [self.linea(quantity=5), self.linea(quantity=6)]
        issues = self.Line._validate_order(once, pedido={'safra_express': True})
        express = [i for i in issues if i['code'] == 'V_EXPRESS_CANTIDAD']
        self.assertEqual(express[0]['line'], 0)
        self.assertEqual(express[0]['severity'], 'error')
        self.assertIn('E20041', express[0]['message'])
        # Sin Safra Express no hay tope.
        self.assertNotIn('V_EXPRESS_CANTIDAD', self.codigos(self.Line._validate_order(once)))

    def test_express_tope_configurable(self):
        self.env['ir.config_parameter'].sudo().set_param('safra.express_max_unidades', '20')
        once = [self.linea(quantity=11)]
        issues = self.Line._validate_order(once, pedido={'safra_express': True})
        self.assertNotIn('V_EXPRESS_CANTIDAD', self.codigos(issues))

    def test_express_llega_a_las_persianas(self):
        quote = self.cotizacion(safra_express=True)
        self.assertTrue(quote.line_ids.safra_express)
        quote.safra_express = False
        self.assertFalse(quote.line_ids.safra_express)

    def test_verificacion_no_bloquea_las_persianas(self):
        fuera = [self.linea(width=3.5)]
        issues = self.Line._validate_order(fuera)
        self.assertIn('V_RANGO_ANCHO', self.codigos(issues, 'error'))
        issues = self.Line._validate_order(fuera, pedido={'requiere_verificacion': True})
        rango = [i for i in issues if i['code'] == 'V_RANGO_ANCHO'][0]
        self.assertEqual(rango['severity'], 'warning')
        self.assertTrue(rango['saltada'])
        self.assertTrue(rango['message'].startswith('Verificación de fabricación: '))

    def test_verificacion_espera_a_produccion(self):
        quote = self.cotizacion(requiere_verificacion=True,
                                verificacion_observaciones='Dos telas blackout')
        ticket = quote._create_verification_ticket()
        self.assertTrue(ticket.safra_verificacion)
        self.assertEqual(quote.verificacion_ticket_id, ticket)
        self.assertIn('Dos telas blackout', ticket.description)
        # Un solo ticket por pedido.
        self.assertFalse(quote._create_verification_ticket())
        quote._update_design_state()
        self.assertEqual(quote.state, 'pending_production')
        with self.assertRaises(UserError):
            quote.action_confirm()
        self.assertFalse(ticket.safra_produccion_aprobada)
        ticket.safra_garantia_motivo = 'Planta revisó el tubo.'
        ticket.action_safra_approve_production()
        self.assertTrue(quote.verificacion_aprobada)
        self.assertTrue(ticket.safra_produccion_aprobada)
        self.assertEqual(quote.state, 'production_approved')
        quote.action_confirm()
        self.assertEqual(quote.state, 'confirmed')

    def test_revalidar_con_verificacion(self):
        quote = self.cotizacion([self.linea(width=3.5)], requiere_verificacion=True)
        errores = [i for i in quote._revalidate() if i['severity'] == 'error']
        self.assertFalse(errores)

    def test_exportacion_avisa_al_grupo(self):
        grupo = self.env.ref('website_quotes_safra.group_safra_exportacion')
        usuario = new_test_user(self.env, login='safra_exportaciones', groups='base.group_user')
        usuario.group_ids |= grupo
        quote = self.cotizacion(es_exportacion=True)
        quote._avisar_exportacion()
        actividad = quote.activity_ids.filtered(lambda a: a.user_id == usuario)
        self.assertEqual(actividad.summary, 'Pedido de exportación: agrupar y facturar')
        normal = self.cotizacion()
        normal._avisar_exportacion()
        self.assertFalse(normal.activity_ids)

    def test_editable_en_portal(self):
        quote = self.cotizacion()
        self.assertTrue(quote.editable_portal)
        quote.state = 'confirmed'
        self.assertFalse(quote.editable_portal)
        self.assertFalse(self.cotizacion(requiere_verificacion=True).editable_portal)
        self.assertFalse(self.cotizacion([self.linea(sin_restricciones=True)]).editable_portal)


@tagged('post_install', '-at_install', 'safra')
class TestPedidoDeVenta(Sprint16Common):
    """Prueba 126.1 (26-oct): la cotización confirmada genera su pedido de
    venta y los de exportación se agrupan con la factura consolidada."""

    def confirmada(self, **vals):
        quote = self.cotizacion([self.linea(price_unit=2700, quantity=2),
                                 self.linea(price_unit=3100, width=2.2, location='Alcoba')], **vals)
        quote.action_confirm()
        self.assertEqual(quote.state, 'confirmed')
        return quote

    def test_pedido_de_venta_al_confirmar(self):
        quote = self.confirmada()
        order = quote.sale_order_id
        self.assertTrue(order)
        self.assertEqual(order.state, 'sale')
        self.assertEqual((order.partner_id, order.origin, order.safra_quote_id),
                         (quote.partner_id, quote.name, quote))
        self.assertEqual(order.order_line.mapped('product_id'),
                         self.enrollable.product_tmpl_id.product_variant_id)
        self.assertEqual([(l.product_uom_qty, l.price_unit) for l in order.order_line],
                         [(2, 2700), (1, 3100)])
        self.assertIn('Alcoba', order.order_line[1].name)
        self.assertFalse(order.safra_exportacion)
        # Confirmar otra vez no crea otro pedido.
        quote._generar_pedido_venta()
        self.assertEqual(self.env['sale.order'].search_count([('safra_quote_id', '=', quote.id)]), 1)

    def test_exportacion_sin_iva(self):
        order = self.confirmada(es_exportacion=True).sale_order_id
        self.assertTrue(order.safra_exportacion)
        self.assertFalse(order.order_line.tax_ids)
        self.assertEqual(order.amount_tax, 0)

    def test_exportacion_con_posicion_fiscal_y_diario(self):
        posicion = self.env['account.fiscal.position'].create({'name': 'Exportación prueba'})
        diario = self.env['account.journal'].create(
            {'name': 'Exportaciones prueba', 'code': 'ZTEXP', 'type': 'sale'})
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('safra.exportacion_posicion_fiscal', posicion.id)
        Param.set_param('safra.exportacion_diario', diario.id)
        order = self.confirmada(es_exportacion=True).sale_order_id
        self.assertEqual((order.fiscal_position_id, order.journal_id), (posicion, diario))
        # Las que no son de exportación no los llevan.
        normal = self.confirmada().sale_order_id
        self.assertNotEqual(normal.fiscal_position_id, posicion)

    def test_factura_consolidada_de_exportacion(self):
        primera = self.confirmada(es_exportacion=True)
        segunda = self.cotizacion([self.linea(price_unit=1000)], es_exportacion=True,
                                  partner_id=primera.partner_id.id)
        segunda.action_confirm()
        pedidos = primera.sale_order_id | segunda.sale_order_id
        wizard = self.env['sale.advance.payment.inv'].with_context(
            active_model='sale.order', active_ids=pedidos.ids).create(
            {'advance_payment_method': 'delivered', 'consolidated_billing': True})
        wizard.create_invoices()
        factura = pedidos.invoice_ids
        self.assertEqual(len(factura), 1)
        self.assertEqual(factura.amount_untaxed, 2700 * 2 + 3100 + 1000)


@tagged('post_install', '-at_install', 'safra')
class TestSprint16Parametrizacion(Sprint16Common):

    def test_itemcode_unico(self):
        Product = self.env['product.template']
        Product.create({'name': 'Insumo A', 'safra_item_code': 'ZT16-0001'})
        with self.assertRaises(ValidationError):
            Product.create({'name': 'Insumo B', 'safra_item_code': 'ZT16-0001'})

    def test_consecutivo_salta_los_usados(self):
        prefijo = self.env['safra.product.option'].create(
            {'type': 'prefijo', 'name': 'ZQ', 'next_number': 1, 'padding': 3})
        self.env['product.template'].create({'name': 'Cargado de SAP', 'safra_item_code': 'ZQ001'})
        nuevo = self.env['product.template'].create({'name': 'Nuevo', 'safra_prefijo': prefijo.id})
        self.assertEqual(nuevo.safra_item_code, 'ZQ002')
        # «[ItemCode] nombre» y el ItemName con el nombre del producto.
        self.assertEqual(nuevo.default_code, 'ZQ002')
        self.assertEqual(nuevo.safra_item_name, 'Nuevo')
        self.assertEqual(prefijo.next_number, 3)

    def test_itemname_propio_se_conserva(self):
        prefijo = self.env['safra.product.option'].create({'type': 'prefijo', 'name': 'ZW'})
        producto = self.env['product.template'].create(
            {'name': 'Persiana Prueba', 'safra_item_name': 'Prueba', 'safra_prefijo': prefijo.id})
        self.assertEqual(producto.safra_item_name, 'Prueba')

    def test_productos_del_kit(self):
        kit = self.env['product.template'].create({'name': 'Kit ZT16'})
        insumo = self.env['product.template'].create({
            'name': 'Insumo del kit', 'safra_kit_asociado_ids': [(6, 0, kit.product_variant_ids.ids)]})
        self.assertEqual(kit.safra_kit_producto_ids, insumo)
        self.assertFalse(insumo.safra_kit_producto_ids)

    def test_unidades_de_negocio(self):
        nombres = self.env['safra.product.option'].search(
            [('type', '=', 'unidad_negocio')]).mapped('name')
        self.assertTrue({'PERSIANAS', 'CORTINA', 'TOLDOS', 'TELAS'} <= set(nombres))

    def test_pesa_lama_desde_referencias(self):
        """Pesa lama se maneja como referencia (categoría Pesa lama); sin
        referencias, el portal sigue con Con / Sin cadenilla."""
        campo = self._campo('pesa_lama')
        self.assertEqual(campo.field_type, 'ref_categoria')
        self.assertEqual(campo.ref_category_id.name, 'Pesa lama')
        self.assertEqual(set(campo.option_ids.mapped('name')), {'Con cadenilla', 'Sin cadenilla'})

    def test_entretela_desde_referencias(self):
        campo = self._campo('tipo_entretela')
        self.assertEqual(campo.field_type, 'ref_categoria')
        self.assertEqual(campo.ref_category_id.name, 'Entretela')
        self.assertEqual(set(campo.option_ids.mapped('value')), {'I100002437', 'I100003009'})

    def test_categoria_puesta_por_safra_se_conserva(self):
        """Una actualización devuelve el campo a lista desplegable; la
        categoría que Safra le haya puesto se mantiene."""
        campo = self._campo('pesa_lama')
        propia = self.env['safra.product.option'].create({'type': 'ref_categoria', 'name': 'Pesas Safra'})
        campo.write({'field_type': 'selection', 'ref_category_id': propia.id})
        self.env['safra.field']._apply_sprint15()
        self.assertEqual(campo.field_type, 'ref_categoria')
        self.assertEqual(campo.ref_category_id, propia)

    def test_orientacion_con_imagen(self):
        self.env['ir.config_parameter'].sudo().set_param('website_quotes_safra.sprint16_orientacion', '')
        campo = self._campo('orientation')
        campo.display_mode = 'auto'
        self.env['safra.field']._apply_sprint16()
        self.assertEqual(campo.display_mode, 'list_thumbs')
        # Una sola vez: lo que Safra cambie después se respeta.
        campo.display_mode = 'list'
        self.env['safra.field']._apply_sprint16()
        self.assertEqual(campo.display_mode, 'list')


@tagged('post_install', '-at_install', 'safra')
class TestPortalSprint16(HttpCase, Sprint16Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usuario = new_test_user(cls.env, login='safra_16_prueba', groups='base.group_portal')

    def setUp(self):
        super().setUp()
        self.authenticate('safra_16_prueba', 'safra_16_prueba')

    def rpc(self, ruta, **params):
        return self.make_jsonrpc_request(ruta, params)

    def formulario(self, n=0, **extra):
        form = {'system_id_%d' % n: self.enrollable.id, 'fabric_id_%d' % n: self.tela.id,
                'color_id_%d' % n: self.blanco.id, 'width_%d' % n: '1.5', 'height_%d' % n: '1.8',
                'quantity_%d' % n: '1', 'location_%d' % n: 'Sala'}
        form.update(extra)
        return form

    def enviar(self, form):
        data = dict(form, csrf_token=http.Request.csrf_token(self))
        return self.url_open('/cotizador/submit', data=data, allow_redirects=False)

    def sin_referencias(self, code):
        self.env['safra.fabric'].search(
            [('category_id', '=', self._campo(code).ref_category_id.id)]).active = False

    def mis_cotizaciones(self):
        return self.env['safra.quote'].search([('partner_id', '=', self.usuario.partner_id.id)])

    def test_pesa_lama_sin_referencias(self):
        self.sin_referencias('pesa_lama')
        sistema = self._sistema('ZT16', 'PRUEBA PESA LAMA', ['width', 'height', 'fabric_id', 'color_id', 'pesa_lama'],
                                (0.30, 3.00, 0.30, 4.00))
        config = self.rpc('/cotizador/ajax/config', system_id=sistema.id)
        pesa = [f for f in config['fields'] if f['code'] == 'pesa_lama'][0]
        self.assertEqual([o['label'] for o in pesa['options']], ['Con cadenilla', 'Sin cadenilla'])

    def test_entretela_sin_referencias(self):
        self.sin_referencias('tipo_entretela')
        sistema = self._sistema('ZT17', 'PRUEBA ENTRETELA', ['width', 'height', 'fabric_id', 'color_id', 'tipo_entretela'],
                                (0.30, 3.00, 0.30, 4.00))
        config = self.rpc('/cotizador/ajax/config', system_id=sistema.id)
        entretela = [f for f in config['fields'] if f['code'] == 'tipo_entretela'][0]
        self.assertEqual({o['value'] for o in entretela['options']}, {'I100002437', 'I100003009'})

    def test_validar_express_del_pedido(self):
        form = self.formulario(quantity_0='11', safra_express='1')
        codigos = [i['code'] for i in self.rpc('/cotizador/ajax/validar', **form)]
        self.assertIn('V_EXPRESS_CANTIDAD', codigos)
        form.pop('safra_express')
        codigos = [i['code'] for i in self.rpc('/cotizador/ajax/validar', **form)]
        self.assertNotIn('V_EXPRESS_CANTIDAD', codigos)

    def test_solo_los_grupos_marcan_exportacion_y_verificacion(self):
        form = self.formulario(width_0='3.5', requiere_verificacion='1',
                               verificacion_observaciones='Ajustar el tubo')
        rango = [i for i in self.rpc('/cotizador/ajax/validar', **form) if i['code'] == 'V_RANGO_ANCHO']
        self.assertEqual(rango[0]['severity'], 'error')
        self.usuario.group_ids |= self.env.ref('website_quotes_safra.group_safra_verificacion')
        rango = [i for i in self.rpc('/cotizador/ajax/validar', **form) if i['code'] == 'V_RANGO_ANCHO']
        self.assertEqual(rango[0]['severity'], 'warning')
        # Sin observaciones no se puede pedir la verificación.
        form.pop('verificacion_observaciones')
        codigos = [i['code'] for i in self.rpc('/cotizador/ajax/validar', **form)]
        self.assertIn('V_VERIFICACION_OBS', codigos)

    def test_guardar_linea_con_verificacion(self):
        """«Guardar línea» valida solo la persiana, pero con lo marcado para
        el pedido: con verificación las restricciones son advertencias."""
        self.usuario.group_ids |= self.env.ref('website_quotes_safra.group_safra_verificacion')
        form = self.formulario(width_0='3.5', requiere_verificacion='1', single=1)
        rango = [i for i in self.rpc('/cotizador/ajax/validar', **form) if i['code'] == 'V_RANGO_ANCHO']
        self.assertEqual(rango[0]['severity'], 'warning')
        # Las observaciones se exigen al finalizar, no al guardar la línea.
        self.assertNotIn('V_VERIFICACION_OBS', [i['code'] for i in self.rpc('/cotizador/ajax/validar', **form)])

    def test_enviar_con_verificacion(self):
        self.usuario.group_ids |= self.env.ref('website_quotes_safra.group_safra_verificacion')
        res = self.enviar(self.formulario(width_0='3.5', requiere_verificacion='1',
                                          verificacion_observaciones='Ajustar el tubo',
                                          acepta_sin_garantia='1'))
        self.assertEqual(res.status_code, 303)
        quote = self.mis_cotizaciones()
        self.assertTrue(quote.requiere_verificacion)
        self.assertEqual(quote.state, 'pending_production')
        self.assertTrue(quote.verificacion_ticket_id)
        self.assertIn('Verificación de fabricación:', quote.verificacion_detalle or '')

    def test_exportacion_no_se_confirma_en_el_portal(self):
        self.usuario.group_ids |= self.env.ref('website_quotes_safra.group_safra_exportacion')
        self.enviar(self.formulario(es_exportacion='1'))
        quote = self.mis_cotizaciones()
        self.assertTrue(quote.es_exportacion)
        self.url_open('/mis-cotizaciones/%d/confirmar' % quote.id,
                      data={'csrf_token': http.Request.csrf_token(self)})
        self.assertEqual(quote.state, 'draft')

    def test_editar_cotizacion(self):
        self.enviar(self.formulario())
        quote = self.mis_cotizaciones()
        self.assertEqual(len(quote.line_ids), 1)
        pagina = self.url_open('/cotizador?editar=%d' % quote.id)
        self.assertIn('safra-edit-data', pagina.text)
        self.assertIn('"width": 1.5', pagina.text)
        form = dict(self.formulario(), **self.formulario(1, width_1='2.0'))
        form['quote_id'] = str(quote.id)
        self.enviar(form)
        self.assertEqual(self.mis_cotizaciones(), quote)
        self.assertEqual(quote.line_ids.sorted('sequence').mapped('width'), [1.5, 2.0])
        # Confirmada ya no se edita.
        quote.state = 'confirmed'
        res = self.url_open('/cotizador?editar=%d' % quote.id, allow_redirects=False)
        self.assertEqual(res.status_code, 303)

    def test_editar_conserva_los_soportes_de_la_secuencia(self):
        """Revisión cálculo de tubo (27-oct, error 4): los soportes del
        configurador de secuencia llegan al editar; sin ellos la secuencia se
        perdía al guardar de nuevo."""
        self.enviar(self.formulario())
        quote = self.mis_cotizaciones()
        quote.line_ids.write({'soporte_izq': 'MANDO', 'soporte_der': 'TERMINAL'})
        pagina = self.url_open('/cotizador?editar=%d' % quote.id)
        self.assertIn('"soporte_izq": "MANDO"', pagina.text)
        self.assertIn('"soporte_der": "TERMINAL"', pagina.text)

    def test_no_edita_cotizaciones_ajenas(self):
        ajena = self.cotizacion()
        res = self.enviar(dict(self.formulario(), quote_id=str(ajena.id)))
        self.assertEqual(res.status_code, 404)

    def excel(self, filas):
        libro = openpyxl.Workbook()
        hoja = libro.active
        for fila in filas:
            hoja.append(fila)
        out = io.BytesIO()
        libro.save(out)
        return out.getvalue()

    def cargar(self, contenido, **extra):
        data = dict({'csrf_token': http.Request.csrf_token(self)}, **extra)
        return self.url_open('/cotizador/cargue', data=data, allow_redirects=False,
                             files={'archivo': ('pedido.xlsx', contenido)})

    def test_plantilla_del_cargue(self):
        res = self.url_open('/cotizador/cargue/plantilla?system_id=%d' % self.enrollable.id)
        libro = openpyxl.load_workbook(io.BytesIO(res.content))
        hoja = libro['Persianas']
        codigos = [c.value for c in hoja[2]]
        self.assertEqual(codigos[0], 'system_id')
        self.assertTrue({'width', 'height', 'fabric_id', 'color_id'} <= set(codigos))
        self.assertEqual(hoja['A3'].value, 'PRUEBA ENROLLABLE')
        opciones = [(r[1], r[2]) for r in libro['Opciones'].iter_rows(min_row=2, values_only=True)]
        self.assertIn(('fabric_id', 'Tela Prueba'), opciones)

    def test_cargue_crea_la_cotizacion(self):
        contenido = self.excel([
            ['Sistema', 'Ancho', 'Alto', 'Cantidad', 'Localización', 'Referencia', 'Color'],
            ['system_id', 'width', 'height', 'quantity', 'location', 'fabric_id', 'color_id'],
            ['PRUEBA ENROLLABLE', 1.5, 1.8, 2, 'Sala', 'Tela Prueba', 'Blanco Prueba'],
            ['prueba enrollable', '2,0', 1.8, 1, 'Alcoba', 'ZT-TELA', 'ZTGRI'],
        ])
        res = self.cargar(contenido)
        self.assertEqual(res.status_code, 303)
        quote = self.mis_cotizaciones()
        lineas = quote.line_ids.sorted('sequence')
        self.assertEqual(lineas.mapped('width'), [1.5, 2.0])
        self.assertEqual(lineas.mapped('color_id'), self.blanco | self.gris)
        self.assertEqual(lineas.mapped('quantity'), [2, 1])

    def test_cargue_con_errores_no_crea_nada(self):
        contenido = self.excel([
            ['Sistema', 'Ancho', 'Alto', 'Referencia', 'Color'],
            ['system_id', 'width', 'height', 'fabric_id', 'color_id'],
            ['PRUEBA ENROLLABLE', 1.5, 1.8, 'Tela Prueba', 'Azul'],
            ['NO EXISTE', 1.5, 1.8, 'Tela Prueba', 'Blanco Prueba'],
            ['PRUEBA ENROLLABLE', 3.5, 1.8, 'Tela Prueba', 'Blanco Prueba'],
        ])
        res = self.cargar(contenido)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Fila 3, Color', res.text)
        self.assertIn('Fila 4: el sistema', res.text)
        self.assertFalse(self.mis_cotizaciones())
        # Con las filas corregidas, el error de rango se reporta por fila.
        contenido = self.excel([
            ['Sistema', 'Ancho', 'Alto', 'Referencia', 'Color'],
            ['system_id', 'width', 'height', 'fabric_id', 'color_id'],
            ['PRUEBA ENROLLABLE', 3.5, 1.8, 'Tela Prueba', 'Blanco Prueba'],
        ])
        res = self.cargar(contenido)
        self.assertIn('Fila 3: ', res.text)
        self.assertFalse(self.mis_cotizaciones())
