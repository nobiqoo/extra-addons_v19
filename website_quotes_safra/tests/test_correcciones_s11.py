# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestAperturaLibre(SafraCommon):
    """Correo de Safra del 19-oct: la Apertura Libre no sale en las
    combinaciones, pero el cliente la puede escoger. Solo se revisa el
    ancho de cada telo; no se exige combinación ni riel."""

    def test_libre_sin_combinacion_ni_riel(self):
        # 3 telos no tienen riel exacto: con otra apertura es E20001.
        self.assertIn('V_PANEL_LAMAS', self.codigos([self.linea_panel(3, 'derecha')]))
        codigos = self.codigos([self.linea_panel(3, 'libre', 'r5')])
        self.assertFalse(codigos & {'V_PANEL_LAMAS', 'V_PANEL_APERTURA', 'V_PANEL_RIEL'}, codigos)

    def test_libre_con_codigo_numerico(self):
        """Panel Japonés usa 5 = Libre."""
        self.assertFalse(self.codigos([self.linea_panel(3, '5')]) & {'V_PANEL_LAMAS', 'V_PANEL_APERTURA'})

    def test_libre_revisa_el_ancho_del_telo(self):
        # 2 telos en 2,40 m dan telos de 1,24 m (máximo 0,95 m).
        issues = self.mensajes([self.linea_panel(2, 'libre')], 'V_PANEL_LAMAS')
        self.assertEqual(len(issues), 1)
        self.assertIn('apertura libre', issues[0]['message'])
        # 12 telos en 2,40 m dan telos de 0,27 m (mínimo 0,35 m).
        self.assertIn('V_PANEL_LAMAS', self.codigos([self.linea_panel(12, 'libre')]))

    def test_libre_no_sale_en_la_tabla(self):
        aperturas = {r['codigo_apertura'] for r in self.env['safra.panel.track'].suggest_configs(
            2.40, 0.08, system=self.panel)}
        self.assertNotIn('libre', aperturas)


@tagged('post_install', '-at_install', 'safra')
class TestRevalidacionServicios(SafraCommon):
    """Revisión del 09-oct (fila 2): al confirmar se valida que la tela y
    los servicios sigan disponibles."""

    def test_tela_ya_no_estampable_bloquea(self):
        self.tela.is_printable = True
        cliente = self.env['res.partner'].create({'name': 'Distribuidor Prueba'})
        quote = self.env['safra.quote'].create({
            'partner_id': cliente.id,
            'line_ids': [(0, 0, dict(self.linea(design_print=True, custom_design='DSPRUEBA'),
                                     sequence=10, design_approved=True))],
        })
        self.tela.is_printable = False
        quote.action_confirm()
        self.assertEqual(quote.state, 'blocked')
        self.assertIn('estampación', quote.bloqueo_motivos)


@tagged('post_install', '-at_install', 'safra')
class TestFormulasFinales(SafraCommon):
    """Las funciones que aplican una sola vez las fórmulas finales de Safra
    (combinaciones y pantógrafos) en las bases existentes."""

    def setUp(self):
        super().setUp()
        self.Param = self.env['ir.config_parameter'].sudo()

    def test_casos_de_pantografos(self):
        vertical = self.env.ref('website_quotes_safra.lru_vertical', raise_if_not_found=False)
        if not vertical:
            self.skipTest('La base no tiene la regla sembrada de Vertical')
        Rule = self.env['safra.lamas.rule']
        vertical.formula_code = vertical.formula_code + ' + 1'
        extra = Rule.create({'system_ids': [(6, 0, vertical.system_ids.ids)],
                             'apertura': 'derecha', 'divisor': 0.08, 'formula_code': '50'})
        self.Param.set_param('website_quotes_safra.pantografos_1910', '')
        Rule._aplicar_casos_pantografos()
        self.assertFalse(extra.active)
        self.assertEqual(vertical.formula_code,
                         Rule.FORMULAS_PANTOGRAFOS['website_quotes_safra.lru_vertical']['formula_code'])
        sistema = vertical.system_ids[:1]
        self.assertEqual([Rule.compute_max(sistema, 3.0, ap) for ap in ('derecha', 'centro', 'extremos')],
                         [37, 38, 38])
        vintage = self.env.ref('website_quotes_safra.lru_vintage', raise_if_not_found=False)
        if vintage:
            self.assertEqual(Rule.compute_max(vintage.system_ids[:1], 2.5, 'centro', motorized=True), 22)


@tagged('post_install', '-at_install', 'safra')
class TestEtiqueta2en1(SafraCommon):

    def test_etiqueta_referencia_1(self):
        mapeo = self.env.ref('website_quotes_safra.sf_32_fabric_id', raise_if_not_found=False)
        if not mapeo:
            self.skipTest('La base no tiene el Enrollable 2 en 1')
        self.assertEqual(mapeo.label_override, 'Referencia 1 tela dentro de cabezal')


@tagged('post_install', '-at_install', 'safra')
class TestColorArchivado(SafraCommon):
    """Un color archivado sigue en la pestaña de la referencia y se
    reactiva desde ahí."""

    def test_color_archivado_se_ve_y_se_reactiva(self):
        self.gris.active = False
        self.assertNotIn(self.gris, self.tela.color_ids)
        self.assertIn(self.gris, self.tela.color_todos_ids)
        self.tela.write({'color_todos_ids': [(1, self.gris.id, {'active': True})]})
        self.assertTrue(self.gris.active)
        self.assertIn(self.gris, self.tela.color_ids)
