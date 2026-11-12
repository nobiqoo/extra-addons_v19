# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon
from ..models import safra_reglas_17 as R17


@tagged('post_install', '-at_install', 'safra')
class TestCenefaTela(SafraCommon):
    """Reunión 28-oct (fila 91): la cenefa en tela sigue las reglas del
    atravesable de la tela de la persiana (rollo de 2,50 m en las pruebas)."""

    def corte(self, **vals):
        attrs = dict({'cenefa_panel': '2'}, **vals.pop('attrs', {}))
        return self.Line.new(dict({
            'system_id': self.enrollable.id, 'fabric_id': self.tela.id, 'color_id': self.blanco.id,
            'width': 2.0, 'height': 1.8, 'quantity': 1, 'attribute_values': attrs}, **vals))

    def test_entera_atravesada_o_anadida(self):
        self.assertEqual(self.corte()._corte_cenefa_tela()['tipo'], 'entera')
        # Supera el rollo con tela no atravesable: añadida.
        self.assertEqual(self.corte(width=2.8)._corte_cenefa_tela()['tipo'], 'anadida')
        # Tela atravesable (Sí o Sí/Cliente): puede cortarse atravesada.
        for tipo in ('si', 'si_cliente'):
            self.tela.pierceable_type = tipo
            self.assertEqual(self.corte(width=2.8)._corte_cenefa_tela()['tipo'], 'atravesada')

    def test_laterales_suman_al_ancho(self):
        self.env['ir.config_parameter'].sudo().set_param('safra.cenefa.lateral', '0.11')
        corte = self.corte(width=2.4, attrs={'cenefa_lateral': 'ambos'})._corte_cenefa_tela()
        self.assertEqual((corte['ancho_cenefa'], corte['tipo']), (2.62, 'anadida'))
        self.env['ir.config_parameter'].sudo().set_param('safra.cenefa.lateral', '0.05')
        self.assertEqual(self.corte(width=2.4, attrs={'cenefa_lateral': 'ambos'})
                         ._corte_cenefa_tela()['tipo'], 'entera')

    def test_solo_cenefa_en_tela(self):
        for panel in ('1', '3', ''):
            corte = self.corte(width=2.8, attrs={'cenefa_panel': panel})._corte_cenefa_tela()
            self.assertEqual((corte['en_tela'], corte['tipo']), (False, ''))

    def test_ajuste_de_las_formulas(self):
        """El ajuste cambia las fórmulas y la condición que siguen como las
        dejó el módulo; una editada por el funcional se respeta."""
        campo = self.env['safra.field'].search([('code', '=', 'corte_cenefa')], limit=1)
        if not campo:
            self.skipTest('La base no tiene el campo Tipo de corte Cenefa Tela')
        anadida = campo.option_ids.filtered(lambda o: o.value == '1')[:1]
        entera = campo.option_ids.filtered(lambda o: o.value == '2')[:1]
        anteriores = {(c, v, t): f for c, v, t, f in R17.FORMULAS_OPCION if c == 'corte_cenefa'}
        anadida.write({'auto_formula': anteriores[('corte_cenefa', '1', 'auto')],
                       'aviso': self.env['safra.field'].AJUSTES_1415_AUTO[('corte_cenefa', '1')][1]})
        entera.write({'formula': 'result = True  # editada', 'auto_formula': False})
        regla = self.env['safra.validation.rule']._por_clave(['V_CENEFA_ENTERA'])[:1]
        regla.write({'condition_code': R17.CAMBIOS['V_CENEFA_ENTERA']['condition'],
                     'message': R17.CAMBIOS['V_CENEFA_ENTERA']['message']})
        self.env['ir.config_parameter'].sudo().set_param('website_quotes_safra.ajuste_cenefa_tela', '')
        regla._ajuste_cenefa_tela()
        self.assertEqual(anadida.auto_formula, R17.CORTE_CENEFA_TELA[('corte_cenefa', '1', 'auto_formula')])
        self.assertEqual(anadida.aviso, R17.CORTE_CENEFA_AVISO)
        self.assertEqual(entera.formula, 'result = True  # editada')
        self.assertEqual(entera.auto_formula, R17.CORTE_CENEFA_TELA[('corte_cenefa', '2', 'auto_formula')])
        self.assertEqual(regla.condition_code, R17.CENEFA_ENTERA_28OCT[0])
        self.assertIn('no se puede atravesar', regla.message)

    def test_portal_elige_y_ofrece_segun_el_corte(self):
        sistema = self.env['safra.system.field'].search(
            [('field_id.code', '=', 'corte_cenefa'), ('active', '=', True)], limit=1).system_id
        if not sistema:
            self.skipTest('Ningún sistema tiene Tipo de corte Cenefa Tela')
        campo = self.env['safra.field'].search([('code', '=', 'corte_cenefa')], limit=1)
        for (code, valor, nombre), formula in R17.CORTE_CENEFA_TELA.items():
            campo.option_ids.filtered(lambda o: o.value == valor)[:1][nombre] = formula
        campo.option_ids.filtered(lambda o: o.value == '1')[:1].aviso = R17.CORTE_CENEFA_AVISO

        def formulas(width):
            return self.corte(system_id=sistema.id, width=width)._formulas_opciones()

        cabe = formulas(2.0)
        self.assertEqual(cabe['auto'].get('corte_cenefa'), '2')
        no_atraviesa = formulas(2.8)
        self.assertEqual(no_atraviesa['auto'].get('corte_cenefa'), '1')
        self.assertNotIn('2', no_atraviesa['opciones']['corte_cenefa'])
        self.assertIn(R17.CORTE_CENEFA_AVISO, no_atraviesa['avisos']['corte_cenefa'])
        self.tela.pierceable_type = 'si'
        atravesada = formulas(2.8)
        self.assertNotIn('corte_cenefa', atravesada['auto'])
        self.assertEqual(set(atravesada['opciones']['corte_cenefa']) & {'1', '2'}, {'1', '2'})

    def test_ayuda_de_las_formulas(self):
        """Revisión 29-oct: la pestaña «Ayuda de las fórmulas» explica cada
        variable que reciben las fórmulas de las opciones."""
        ayuda = str(self.env['safra.field'].search([('code', '=', 'corte_cenefa')], limit=1).ayuda_formulas
                    or self.env['safra.field'].new({}).ayuda_formulas)
        maps = self.env['safra.system.field'].search([('system_id', '=', self.enrollable.id)])
        ctx = self.corte()._ctx_formulas_opciones(maps)
        campos = set(self.env['safra.field'].with_context(active_test=False).search([]).mapped('code'))
        propias = [k for k in ctx if k not in campos and not k.startswith('ancho_max_')]
        self.assertIn('tipo_corte_cenefa', propias)
        for nombre in propias:
            self.assertIn(nombre, ayuda, 'La variable %s no está en la ayuda' % nombre)
        self.assertIn("'anadida'", ayuda)
        self.assertTrue(self.env['safra.system.field'].new({}).ayuda_formulas)
