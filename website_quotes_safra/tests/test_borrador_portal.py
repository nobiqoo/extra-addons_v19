# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import UserError
from odoo.tests import HttpCase, new_test_user, tagged

from .test_ajustes_16 import Ajustes16Common


@tagged('post_install', '-at_install', 'safra')
class TestBorradorPortal(HttpCase, Ajustes16Common):
    """Revisión 27-oct (pruebas de Safra): el pedido se guarda como
    borrador aunque tenga errores; no se finaliza ni se confirma hasta
    corregirlos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usuario = new_test_user(cls.env, login='safra_borr', groups='base.group_portal')

    def setUp(self):
        super().setUp()
        self.authenticate('safra_borr', 'safra_borr')

    def formulario(self, **extra):
        form = {'system_id_0': self.enrollable.id, 'fabric_id_0': self.tela.id,
                'color_id_0': self.blanco.id, 'width_0': '1.5', 'height_0': '1.8',
                'quantity_0': '1', 'location_0': 'Sala'}
        form.update(extra)
        return form

    def post(self, ruta, data=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(ruta, data=data, allow_redirects=False)

    def mis_cotizaciones(self):
        return self.env['safra.quote'].search([('partner_id', '=', self.usuario.partner_id.id)])

    def test_finalizar_con_errores_no_guarda(self):
        res = self.post('/cotizador/submit', self.formulario(width_0='0.2'))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(self.mis_cotizaciones())

    def test_borrador_con_errores(self):
        res = self.post('/cotizador/submit', self.formulario(width_0='0.2', guardar_borrador='1'))
        self.assertEqual(res.status_code, 303)
        quote = self.mis_cotizaciones()
        self.assertEqual(quote.state, 'draft')
        self.assertTrue(quote.borrador_portal)
        self.assertTrue(quote.borrador_errores.startswith('Persiana 1: '))
        self.assertTrue(quote.editable_portal)
        detalle = self.url_open('/mis-cotizaciones/%d' % quote.id).text
        self.assertIn('Borrador sin finalizar', detalle)
        self.assertNotIn('Confirmar pedido', detalle)
        # Ni forzando la ruta se confirma.
        self.post('/mis-cotizaciones/%d/confirmar' % quote.id)
        self.assertEqual(quote.state, 'draft')

    def test_borrador_no_arranca_flujos_hasta_finalizar(self):
        self.usuario.group_ids |= (self.env.ref('website_quotes_safra.group_safra_verificacion')
                                   | self.env.ref('website_quotes_safra.group_safra_exportacion'))
        self.env.ref('website_quotes_safra.group_safra_exportacion').user_ids |= self.env.ref('base.user_admin')
        pedido = {'requiere_verificacion': '1', 'verificacion_observaciones': 'Ajustar el tubo',
                  'es_exportacion': '1', 'acepta_sin_garantia': '1'}
        self.post('/cotizador/submit', self.formulario(width_0='0.2', guardar_borrador='1', **pedido))
        quote = self.mis_cotizaciones()
        self.assertFalse(quote.verificacion_ticket_id)
        self.assertFalse(quote.activity_ids)
        self.assertTrue(quote.editable_portal)
        # Corregido y finalizado: arrancan la verificación y el aviso a exportaciones.
        res = self.post('/cotizador/submit', dict(self.formulario(**pedido), quote_id=str(quote.id)))
        self.assertEqual(res.status_code, 303)
        self.assertFalse(quote.borrador_portal)
        self.assertFalse(quote.borrador_errores)
        self.assertTrue(quote.verificacion_ticket_id)
        self.assertEqual(quote.state, 'pending_production')
        self.assertTrue(quote.activity_ids)

    def test_persiana_sin_color_no_se_guarda(self):
        self.post('/cotizador/submit', self.formulario(
            guardar_borrador='1', system_id_1=self.enrollable.id, fabric_id_1=self.tela.id,
            width_1='1.2', height_1='1.5', quantity_1='1', location_1='Cocina'))
        quote = self.mis_cotizaciones()
        self.assertEqual(len(quote.line_ids), 1)
        self.assertIn('Persiana 2: Sin referencia y color', quote.borrador_errores)

    def test_sin_persianas_completas_no_guarda(self):
        res = self.post('/cotizador/submit', self.formulario(color_id_0='', guardar_borrador='1'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('Para guardar el borrador', res.text)
        self.assertFalse(self.mis_cotizaciones())

    def test_backoffice_y_tarea_programada(self):
        self.post('/cotizador/submit', self.formulario(width_0='0.2', guardar_borrador='1'))
        quote = self.mis_cotizaciones()
        with self.assertRaisesRegex(UserError, 'no ha finalizado'):
            quote.action_confirm()
        # La revisión de vigencia no anula el borrador: lo corrige el cliente.
        self.env['safra.quote']._cron_anular_invalidas()
        self.assertEqual(quote.state, 'draft')
