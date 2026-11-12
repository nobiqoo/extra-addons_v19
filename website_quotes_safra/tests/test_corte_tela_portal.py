# -*- coding: utf-8 -*-
from odoo.tests import HttpCase, new_test_user, tagged

from .common import SafraCommon
from ..models import safra_reglas_17 as R17


class CorteTelaComun(SafraCommon):
    """Reglas del corte de la tela como las deja el módulo (archivos de
    Safra «Tipos de corte tela»), en el enrollable de prueba."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Param = cls.env['ir.config_parameter'].sudo()
        cls.enrollable.calculo_corte = 'persiana'
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
        Rule.search([('code', 'in', ('V_ANADIDO', 'V_CORTE_ATRAVESADO'))]).severity = 'warning'
        r = R17.SIN_ANCHO_ROLLO
        vals = {'condition_code': r['condition'], 'message': r['message'], 'active': True,
                'severity': 'error', 'momento': 'linea', 'system_ids': [(5, 0, 0)]}
        regla = Rule._por_clave([r['code']])
        if regla:
            regla.write(vals)
        else:
            Rule.create(dict(vals, code=r['code'], name=r['name']))
        cls.Rule = Rule

    def avisos(self, **vals):
        return self.Line._avisos_corte(self.linea(**vals))

    def codigos_corte(self, res):
        return [(a['code'], a['severity']) for a in res['avisos']]


@tagged('post_install', '-at_install', 'safra')
class TestAvisosCorte(CorteTelaComun):
    """Revisión 30-oct (tela atravesable y U_Añadido): el portal muestra el
    tipo de corte y los mensajes de sus reglas junto a la tela mientras se
    digita; si no se puede fabricar, no deja seguir."""

    def test_corte_normal_sin_avisos(self):
        res = self.avisos(width=2.4)
        self.assertEqual((res['tipo'], res['avisos'], res['bloquea']), ('normal', [], False))

    def test_no_atravesable_mas_ancha_que_el_rollo_bloquea(self):
        res = self.avisos(width=2.6)
        self.assertEqual(res['tipo'], 'no_fabricable')
        self.assertEqual(self.codigos_corte(res), [('V_ANCHO_ROLLO', 'error')])
        self.assertIn('no es atravesable', res['avisos'][0]['message'])
        self.assertTrue(res['bloquea'])

    def test_atravesada_avisa_sin_bloquear(self):
        self.tela.pierceable_type = 'si'
        res = self.avisos(width=2.6, height=2.2)
        self.assertEqual(res['tipo'], 'atravesado')
        self.assertEqual(self.codigos_corte(res), [('V_CORTE_ATRAVESADO', 'warning')])
        self.assertFalse(res['bloquea'])
        # Con la aceptación marcada, la condición de la regla ya no se cumple.
        self.assertEqual(self.avisos(width=2.6, height=2.2, acepta_atravesado=True)['avisos'], [])

    def test_atravesable_que_no_cabe_ni_atravesada_bloquea(self):
        """La aceptación no aplica: el portal la oculta (tipo no_fabricable)."""
        self.tela.pierceable_type = 'si'
        res = self.avisos(width=2.6, height=2.6)
        self.assertEqual(res['tipo'], 'no_fabricable')
        self.assertEqual(self.codigos_corte(res), [('V_ANCHO_ROLLO', 'error')])
        self.assertTrue(res['bloquea'])

    def test_anadido_avisa_y_exceso_bloquea(self):
        self.tela.write({'pierceable_type': 'si', 'is_anadido': True})
        res = self.avisos(width=2.6, height=2.6)
        self.assertEqual(res['tipo'], 'anadido')
        self.assertEqual(self.codigos_corte(res), [('V_ANADIDO', 'warning')])
        self.assertFalse(res['bloquea'])
        res = self.avisos(width=2.6, height=4.9)
        self.assertEqual(res['tipo'], 'anadido_excede')
        self.assertEqual(self.codigos_corte(res), [('V_ANADIDO_MAXIMO', 'error')])
        self.assertTrue(res['bloquea'])

    def test_lo_configurado_en_validaciones_manda(self):
        regla = self.Rule.search([('code', '=', 'V_ANCHO_ROLLO')])
        regla.message = 'La configuración de la Persiana seleccionada NO se puede Fabricar'
        self.assertEqual(self.avisos(width=2.6)['avisos'][0]['message'],
                         'La configuración de la Persiana seleccionada NO se puede Fabricar [V_ANCHO_ROLLO]')
        # Como advertencia avisa pero no bloquea.
        regla.severity = 'warning'
        self.assertFalse(self.avisos(width=2.6)['bloquea'])
        # Inactiva no sale.
        regla.active = False
        res = self.avisos(width=2.6)
        self.assertEqual((res['tipo'], res['avisos'], res['bloquea']), ('no_fabricable', [], False))

    def test_solo_las_reglas_del_corte(self):
        """Las demás reglas de la línea salen al guardarla, no aquí."""
        self.assertIn('V_RANGO_ALTO', self.codigos([self.linea(width=2.6, height=4.5)], cross=False))
        res = self.avisos(width=2.6, height=4.5)
        self.assertEqual([a['code'] for a in res['avisos']], ['V_ANCHO_ROLLO'])

    def test_sin_restricciones_no_bloquea(self):
        res = self.avisos(width=2.6, sin_restricciones=True)
        self.assertEqual(self.codigos_corte(res), [('V_ANCHO_ROLLO', 'warning')])
        self.assertFalse(res['bloquea'])

    def test_color_sin_ancho_del_rollo(self):
        """Revisión 30-oct (U_Ancho): sin dato vale 0 y no se toma el de otro
        color de la referencia (Blanco tiene 2,50 m)."""
        sin_dato = self._color(self.tela, 'ZT-SINU', 'Sin U_Ancho')
        # 9-nov: sin digitar (vacío) y digitado en 0 dicen cosas distintas.
        sin_dato.product_tmpl_id.safra_u_ancho = False
        res = self.avisos(width=1.5, color_id=sin_dato.id)
        self.assertEqual(res['tipo'], 'sin_ancho_rollo')
        self.assertEqual(self.codigos_corte(res), [('V_SIN_ANCHO_ROLLO', 'error')])
        self.assertIn('Sin U_Ancho no tiene digitado el ancho del rollo (U_Ancho)', res['avisos'][0]['message'])
        sin_dato.product_tmpl_id.safra_u_ancho = 0
        res = self.avisos(width=1.5, color_id=sin_dato.id)
        self.assertIn('Sin U_Ancho tiene el ancho del rollo (U_Ancho) en 0', res['avisos'][0]['message'])
        self.assertTrue(res['bloquea'])
        self.assertIn('V_SIN_ANCHO_ROLLO', self.codigos([self.linea(color_id=sin_dato.id)], cross=False))
        # Como advertencia avisa y deja seguir.
        self.Rule._por_clave(['V_SIN_ANCHO_ROLLO']).severity = 'warning'
        res = self.avisos(width=1.5, color_id=sin_dato.id)
        self.assertEqual((self.codigos_corte(res), res['bloquea']), ([('V_SIN_ANCHO_ROLLO', 'warning')], False))
        # Con el dato en el producto, el corte se calcula con él.
        sin_dato.product_tmpl_id.safra_u_ancho = 1.4
        self.assertEqual(self.avisos(width=1.5, color_id=sin_dato.id)['tipo'], 'no_fabricable')

    def test_sistema_sin_calculo_de_corte(self):
        """Revisión 30-oct: el cálculo lo elige el sistema; vacío, no hay
        corte ni reglas del corte."""
        self.enrollable.calculo_corte = False
        self.assertEqual(self.avisos(width=2.6),
                         {'tipo': '', 'avisos': [], 'avisos_ficha': [], 'bloquea': False})
        self.enrollable.product_tmpl_id.safra_calculo_corte = 'persiana'
        self.assertEqual(self.avisos(width=2.6)['tipo'], 'no_fabricable')

    def test_ajuste_marca_los_sistemas_actuales(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.search([('key', '=', 'website_quotes_safra.ajuste_calculo_corte')]).unlink()
        Param.set_param('safra.corte.sistemas_cortina', 'ZT01')
        self.enrollable.calculo_corte = False
        self.env['safra.system']._ajuste_calculo_corte()
        self.assertEqual(self.enrollable.calculo_corte, 'cortina')
        self.assertFalse(Param.get_param('safra.corte.sistemas_cortina'))
        # Una sola vez: lo que se cambie después se respeta.
        self.enrollable.calculo_corte = 'persiana'
        self.env['safra.system']._ajuste_calculo_corte()
        self.assertEqual(self.enrollable.calculo_corte, 'persiana')

    def test_al_guardar_la_linea_siguen_saliendo(self):
        self.assertIn('V_ANCHO_ROLLO', self.codigos([self.linea(width=2.6)], cross=False))

    def test_al_digitar_no_salen_debajo_del_campo(self):
        """Una regla del corte «Al digitar un campo» sale junto a la tela,
        no debajo del Ancho."""
        self.Rule.search([('code', '=', 'V_ANCHO_ROLLO')]).write(
            {'momento': 'campo', 'trigger_field_id': self._campo('width').id})
        issues = self.Line._validate_order([self.linea(width=2.6)], cross=False, campo='width')
        self.assertNotIn('V_ANCHO_ROLLO', {i['code'] for i in issues})
        self.assertEqual(self.codigos_corte(self.avisos(width=2.6)), [('V_ANCHO_ROLLO', 'error')])


@tagged('post_install', '-at_install', 'safra')
class TestAvisosCortePortal(HttpCase, CorteTelaComun):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        new_test_user(cls.env, login='safra_portal_corte', groups='base.group_portal')

    def setUp(self):
        super().setUp()
        self.authenticate('safra_portal_corte', 'safra_portal_corte')

    def test_endpoint_corte_tela(self):
        datos = {'system_id_0': self.enrollable.id, 'fabric_id_0': self.tela.id,
                 'color_id_0': self.blanco.id, 'width_0': '2.6', 'height_0': '1.8',
                 'quantity_0': '1', 'location_0': 'Sala'}
        res = self.make_jsonrpc_request('/cotizador/ajax/corte_tela', datos)
        self.assertEqual((res['tipo'], res['bloquea']), ('no_fabricable', True))
        self.assertEqual([a['code'] for a in res['avisos']], ['V_ANCHO_ROLLO'])
        # Sin tela todavía no hay corte.
        res = self.make_jsonrpc_request('/cotizador/ajax/corte_tela',
                                        dict(datos, fabric_id_0='', color_id_0=''))
        self.assertEqual(res, {'tipo': '', 'avisos': [], 'avisos_ficha': [], 'bloquea': False})
