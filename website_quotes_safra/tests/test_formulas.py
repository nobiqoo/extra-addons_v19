# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.website_quotes_safra.models.safra_panel import (
    evaluar_formula, variables_formulario)

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestCombinacionesPanel(SafraCommon):
    """Combinaciones de Panel Track con la fórmula del Excel de Safra
    (revisión 10-nov). Los valores esperados son los del Excel de Safra
    (Panel_Track_Best_Fit_Odoo_CORREGIDO, hoja «Matriz 2-12»)."""

    def combos(self, ancho=2.40, traslape=0.08, campos=None):
        rows = self.env['safra.panel.track'].suggest_configs(
            ancho, traslape, campos=campos, system=self.panel)
        return {(r['total_telos'], r['codigo_apertura'], r['canales'],
                 r['codigo_condicion']) for r in rows}

    def test_combinaciones_240_con_traslape_8(self):
        """2,40 m con 8 cm: 12 combinaciones con la fórmula final de Safra
        (correo del 19-oct: Centro usa tantos canales como telos); 7 telos
        van con Riel Velcrado."""
        self.assertEqual(self.combos(), {
            (4, 'unilateral_derecha', 4, 'estandar'),
            (4, 'unilateral_izquierda', 4, 'estandar'),
            (4, 'centro', 4, 'estandar'),
            (5, 'unilateral_derecha', 5, 'estandar'),
            (5, 'unilateral_izquierda', 5, 'estandar'),
            (6, 'unilateral_derecha', 6, 'estandar'),
            (6, 'unilateral_izquierda', 6, 'estandar'),
            (6, 'centro', 6, 'estandar'),
            (6, 'extremos', 4, 'estandar'),
            (7, 'unilateral_derecha', 6, 'riel_velcrado'),
            (7, 'unilateral_izquierda', 6, 'riel_velcrado'),
            (8, 'extremos', 5, 'estandar'),
        })

    def test_ancho_de_cada_telo(self):
        rows = self.env['safra.panel.track'].compute_configs(2.40, 0.08, 6, system=self.panel)
        self.assertTrue(rows)
        self.assertAlmostEqual(rows[0]['ancho_telo_cm'], 46.67, places=2)

    def test_sin_riel_exacto_no_hay_combinacion(self):
        """3 telos necesitan 3 canales y no hay riel de 3."""
        Track = self.env['safra.panel.track']
        self.assertEqual(Track.compute_configs(2.40, 0.08, 3, system=self.panel), [])
        # 2 telos de 1,24 m superan el máximo de 0,95 m por telo.
        self.assertEqual(Track.compute_configs(2.40, 0.08, 2, system=self.panel), [])

    def test_centro_y_extremos_solo_pares(self):
        aperturas_impares = {a for t, a, _c, _v in self.combos() if t % 2}
        self.assertFalse(aperturas_impares & {'centro', 'extremos'})

    def test_extremos_12_telos_riel_velcrado(self):
        rows = self.env['safra.panel.track'].compute_configs(6.0, 0.08, 12, system=self.panel)
        extremos = [r for r in rows if r['codigo_apertura'] == 'extremos']
        self.assertEqual(len(extremos), 1)
        self.assertEqual(extremos[0]['canales'], 6)
        self.assertEqual(extremos[0]['codigo_condicion'], 'riel_velcrado')

    def test_rango_viable(self):
        Track = self.env['safra.panel.track']
        rango = Track.viable_width_range(0.08, system=self.panel)
        self.assertEqual((rango['wmin'], rango['wmax']), (1.16, 8.0))
        rango6 = Track.viable_width_range(0.08, telos=6, system=self.panel)
        self.assertEqual((rango6['wmin'], rango6['wmax']), (1.70, 5.29))
        self.assertTrue(Track.viable_width_range(0.08, telos=3, system=self.panel).get('sin_riel'))

    def test_apertura_libre_solo_si_se_ofrece(self):
        """Correo del 19-oct: la Apertura Libre no sale del Excel (no tiene
        riel fijo); si se ofrece, el portal la muestra."""
        self.assertNotIn('libre', self.combo_rule._aperturas())
        self.combo_rule.ofrecer_libre = True
        self.assertIn('libre', self.combo_rule._aperturas())
        self.assertNotIn('libre', {a for _t, a, _c, _v in self.combos()})

    def test_formula_del_ancho_con_error_no_se_guarda(self):
        with self.assertRaises(ValidationError):
            self.combo_rule.formula_ancho_telo = 'ancho +'


@tagged('post_install', '-at_install', 'safra')
class TestEvaluarFormula(SafraCommon):

    def test_una_linea_y_bloque(self):
        self.assertEqual(evaluar_formula('telos * 2', {'telos': 3})[0], 6)
        valor, variables = evaluar_formula('x = telos * 2\nresult = x + 1', {'telos': 3})
        self.assertEqual(valor, 7)
        self.assertEqual(variables['x'], 6)
        self.assertEqual(evaluar_formula('', {}), (None, {}))

    def test_variables_formulario(self):
        out = variables_formulario(
            {'height': '2,5', 'has_motor': True, 'riel_tipo': 'r6', 'Mal-Nombre': 1, 'telos': 99},
            {'telos': 4})
        self.assertEqual(out['height'], 2.5)
        self.assertEqual(out['has_motor'], 1.0)
        self.assertEqual(out['riel_tipo'], 'r6')
        self.assertNotIn('Mal-Nombre', out)
        # Nunca reemplaza una variable propia de la fórmula.
        self.assertNotIn('telos', out)


@tagged('post_install', '-at_install', 'safra')
class TestMaximoLamas(SafraCommon):
    """Máximo total de lamas o pantógrafos con las fórmulas y los casos de
    prueba del archivo de Safra (correo del 19-oct, CALCULO PANTOGRAFOS):
    redondeo como Excel y par hacia arriba donde el archivo lo pide."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        System = cls.env['safra.system']
        Rule = cls.env['safra.lamas.rule']
        formulas = Rule.FORMULAS_PANTOGRAFOS
        cls.vertical = System.create({'code': 'ZT40', 'name': 'PRUEBA VERTICAL'})
        cls.vintage = System.create({'code': 'ZT42', 'name': 'PRUEBA VINTAGE'})
        cls.sencilla = System.create({'code': 'ZT63', 'name': 'PRUEBA VINTAGE SENCILLA'})
        cls.regla_vertical = Rule.create(dict(
            formulas['website_quotes_safra.lru_vertical'], system_ids=[(6, 0, cls.vertical.ids)]))
        Rule.create(dict(formulas['website_quotes_safra.lru_vintage'],
                         system_ids=[(6, 0, cls.vintage.ids)]))
        Rule.create(dict(formulas['website_quotes_safra.lru_vintage_std'],
                         system_ids=[(6, 0, cls.sencilla.ids)]))

    def maximo(self, system, ancho, apertura, motor=False):
        return self.env['safra.lamas.rule'].compute_max(system, ancho, apertura, motorized=motor)

    def casos(self, system, ancho):
        return [self.maximo(system, ancho, ap) for ap in ('derecha', 'centro', 'extremos')]

    def test_casos_del_archivo_de_safra(self):
        """Las filas PRUEBA del archivo: Vertical 3 m, Vintage 2,5 m y
        Vintage Sencilla 3 m (Derecha/Izquierda, Centro, Extremos)."""
        self.assertEqual(self.casos(self.vertical, 3.0), [37, 38, 38])
        self.assertEqual(self.casos(self.vintage, 2.5), [22, 22, 22])
        self.assertEqual(self.casos(self.sencilla, 3.0), [14, 14, 16])

    def test_vintage_sencilla_par_solo_en_extremos(self):
        # Mejoras Sprint 1.1 (21-oct, fila 18): 2,00 m → 9, 9 y 10.
        self.assertEqual(self.casos(self.sencilla, 2.0), [9, 9, 10])

    def test_redondeo_como_excel(self):
        """El ,5 sube (Python redondeaba al par: 12,5 daba 12)."""
        self.assertEqual(self.maximo(self.vertical, 1.0, 'centro'), 13)
        self.assertEqual(self.maximo(self.vertical, 1.0, 'derecha'), 12)
        # Extremos: siguiente par hacia arriba (12,85 → 14).
        self.assertEqual(self.maximo(self.vertical, 1.0, 'extremos'), 14)

    def test_vintage_igual_con_o_sin_motor(self):
        self.assertEqual(self.maximo(self.vintage, 2.5, 'centro', motor=True),
                         self.maximo(self.vintage, 2.5, 'centro'))

    def test_vintage_sencilla_par_en_extremos(self):
        # Mejoras Sprint 1.1 (21-oct, fila 18): como las celdas del Excel y lo
        # aprobado por Safra, el par solo se asegura en extremos.
        for ancho in (1.5, 2.0, 2.7, 3.3):
            self.assertEqual(self.maximo(self.sencilla, ancho, 'extremos') % 2, 0, ancho)

    def test_sin_regla_no_hay_maximo(self):
        self.assertIsNone(self.maximo(self.enrollable, 1.0, 'centro'))

    def test_regla_mas_especifica_gana(self):
        self.env['safra.lamas.rule'].create({
            'system_ids': [(6, 0, self.vertical.ids)], 'apertura': 'centro',
            'divisor': 1, 'formula_code': '99'})
        self.assertEqual(self.maximo(self.vertical, 1.0, 'centro'), 99)
        self.assertEqual(self.maximo(self.vertical, 1.0, 'derecha'), 12)

    def test_formula_con_error_no_se_guarda(self):
        with self.assertRaises(ValidationError):
            self.regla_vertical.formula_code = '(ancho - aux) /'
