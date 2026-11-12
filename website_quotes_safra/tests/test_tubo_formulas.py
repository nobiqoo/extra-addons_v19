# -*- coding: utf-8 -*-
import math

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import SafraCommon
from ..models import safra_reglas_17 as R17


@tagged('post_install', '-at_install', 'safra')
class TestTuboFormulas(SafraCommon):
    """Revisión 30-oct: las fórmulas de alto y peso máximo del tubo se ven y
    se cambian en Ajustes › Tubo: alto y peso máximo. Fila R8 manual de
    prueba: espacio 60 mm, diámetro 40 mm, carga 2.000 g."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().search(
            [('key', 'in', list(R17.FORMULAS_TUBO))]).unlink()

    def limites(self, **kw):
        vals = dict(peso_tela=300.0, grosor_tela=0.5, peso_perfil=136.0, factor=1.0)
        vals.update(kw)
        return self.r8_manual.compute_limits(1.5, 1.8, **vals)

    def test_por_defecto_da_lo_mismo_que_antes(self):
        lim = self.limites()
        espacio = ((60 - 40 / 2.0) / 0.5) * (math.pi * 40) / 1000.0
        carga = (2000 - 1.5 * 136) / (300 * 1.5)
        self.assertEqual(lim['alto_maximo'], round(min(espacio, carga), 2))
        self.assertEqual(lim['alto_limitante'], 'carga')
        self.assertEqual(lim['peso_total'], round(1.5 * 1.8 * 300 + 136 * 1.5, 0))
        self.assertTrue(lim['alto_ok'])
        # Sin peso ni grosor de la tela no se calcula.
        vacio = self.limites(peso_tela=0.0, grosor_tela=0.0)
        self.assertEqual((vacio['alto_maximo'], vacio['peso_total']), (None, None))

    def test_el_perfil_cambia_el_alto_por_carga(self):
        sin_perfil = self.limites(peso_perfil=0.0)['alto_maximo']
        con_perfil = self.limites(peso_perfil=346.0)['alto_maximo']
        self.assertGreater(sin_perfil, con_perfil)

    def test_la_formula_se_cambia_en_ajustes(self):
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('safra.formula.tubo_alto_carga',
                        'result = (carga_maxima - ancho * peso_perfil) / (peso_tela * factor * ancho) - 0.5')
        carga = (2000 - 1.5 * 136) / (300 * 1.5) - 0.5
        self.assertEqual(self.limites()['alto_maximo'], round(carga, 2))
        Param.set_param('safra.formula.tubo_peso_total', 'result = ancho * alto * peso_tela * factor')
        self.assertEqual(self.limites()['peso_total'], 810)
        # Una fórmula con error no rompe el portal: ese valor no se calcula.
        Param.set_param('safra.formula.tubo_alto_carga', 'result = no_existe * 2')
        self.assertEqual(self.limites()['alto_limitante'], 'espacio')

    def test_ajustes_muestran_y_revisan_las_formulas(self):
        Settings = self.env['res.config.settings']
        self.assertEqual(Settings.create({}).safra_formula_tubo_peso_total,
                         R17.FORMULAS_TUBO['safra.formula.tubo_peso_total'])
        with self.assertRaisesRegex(ValidationError, 'No existe la variable «peso»'):
            Settings.create({'safra_formula_tubo_peso_total': 'result = peso * 2'}).execute()
        # Los campos del cotizador no llegan a estas fórmulas: no se aceptan.
        with self.assertRaisesRegex(ValidationError, 'No existe la variable «apertura»'):
            Settings.create({'safra_formula_tubo_alto_carga': "result = 2 if apertura == '1' else 3"}).execute()
        Settings.create({'safra_formula_tubo_peso_total': 'result = ancho * alto * peso_tela'}).execute()
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param('safra.formula.tubo_peso_total'),
                         'result = ancho * alto * peso_tela')
