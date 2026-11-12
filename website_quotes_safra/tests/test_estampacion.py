# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestEstampacionFueraDeServicio(SafraCommon):
    """Revisión 27-oct: «Inhabilitar servicios de estampación» en Ajustes
    enciende la regla V_ESTAMPADO_FUERA_SERVICIO."""

    def setUp(self):
        super().setUp()
        self.regla = self.env['safra.validation.rule'].with_context(active_test=False).search(
            [('code', '=', 'V_ESTAMPADO_FUERA_SERVICIO')])
        self.regla.write({'active': False, 'condition_code': 'design_print', 'momento': 'linea',
                          'message': 'E13095: Temporalmente, los estampados están FUERA DE SERVICIO.'})

    def ajustes(self, valor):
        settings = self.env['res.config.settings'].create({'safra_estampado_fuera_servicio': valor})
        settings.execute()

    def test_la_casilla_enciende_y_apaga_la_regla(self):
        estampado = self.linea(design_print=True)
        self.assertFalse(self.env['res.config.settings'].create({}).safra_estampado_fuera_servicio)
        self.assertNotIn('V_ESTAMPADO_FUERA_SERVICIO', self.codigos([estampado]))
        self.ajustes(True)
        self.assertTrue(self.regla.active)
        self.assertTrue(self.env['res.config.settings'].create({}).safra_estampado_fuera_servicio)
        self.assertIn('V_ESTAMPADO_FUERA_SERVICIO', self.codigos([estampado]))
        # Sin estampado, nada cambia.
        self.assertNotIn('V_ESTAMPADO_FUERA_SERVICIO', self.codigos([self.linea()]))
        self.ajustes(False)
        self.assertFalse(self.regla.active)
        self.assertNotIn('V_ESTAMPADO_FUERA_SERVICIO', self.codigos([estampado]))


@tagged('post_install', '-at_install', 'safra')
class TestAnchoMaximoImpresion(SafraCommon):
    """Revisión 27-oct: el ancho máximo de impresión de Sheer Elegance sale
    de Ajustes › Cotizador Safra › Estampación."""

    CONDICION = 'maximo = ancho_max_impresion\nresult = design_print and ancho > maximo'

    def setUp(self):
        super().setUp()
        self.regla = self.env['safra.validation.rule'].with_context(active_test=False).search(
            [('code', '=', 'V_ESTAMPADO_SHEER_ELEGANCE')])
        self.regla.write({'active': True, 'condition_code': self.CONDICION,
                          'message': 'E13095: El ancho máximo para estampación es de {maximo} metros.'})

    def mensajes_estampado(self, ancho):
        return self.mensajes([self.linea(design_print=True, width=ancho)], 'V_ESTAMPADO_SHEER_ELEGANCE')

    def test_el_ancho_de_ajustes_manda(self):
        self.env['ir.config_parameter'].sudo().set_param('safra.estampado.ancho_max', False)
        self.assertFalse(self.mensajes_estampado(2.4))  # sin valor rige 2,5 m
        self.env['res.config.settings'].create({'safra_estampado_ancho_max': 2.0}).execute()
        mensajes = self.mensajes_estampado(2.4)
        self.assertEqual([m['message'] for m in mensajes],
                         ['E13095: El ancho máximo para estampación es de 2.0 metros.'])
        self.assertFalse(self.mensajes_estampado(1.9))
        self.assertFalse(self.mensajes([self.linea(width=2.4)], 'V_ESTAMPADO_SHEER_ELEGANCE'))

    def test_ajuste_de_la_condicion_una_sola_vez(self):
        Rule = self.env['safra.validation.rule']
        Param = self.env['ir.config_parameter'].sudo()
        sembrada = 'maximo = 2.5\nresult = design_print and ancho > maximo'
        self.regla.condition_code = sembrada
        Param.set_param('website_quotes_safra.ajuste_ancho_impresion', False)
        Rule._ajuste_ancho_impresion()
        self.assertEqual(self.regla.condition_code, self.CONDICION)
        # Una condición editada por el funcional no se toca.
        editada = 'maximo = 2.2\nresult = design_print and ancho > maximo'
        self.regla.condition_code = editada
        Param.set_param('website_quotes_safra.ajuste_ancho_impresion', False)
        Rule._ajuste_ancho_impresion()
        self.assertEqual(self.regla.condition_code, editada)
