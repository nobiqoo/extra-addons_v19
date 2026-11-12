# -*- coding: utf-8 -*-
import base64
import io

import openpyxl
from openpyxl.worksheet.formula import ArrayFormula

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import COMBINACIONES_SAFRA, SafraCommon, excel_safra
from ..models import excel_formula


def excel_cambiado(*cambios, titulos=None, etiqueta=None):
    """El Excel de Safra con la fórmula del Configurador cambiada (pares
    texto viejo → texto nuevo), como si Safra la editara en Excel."""
    libro = openpyxl.load_workbook(io.BytesIO(excel_safra()))
    hoja = libro['Configurador']
    formula = hoja['A5'].value
    texto = formula.text
    for viejo, nuevo in cambios:
        assert viejo in texto, viejo
        texto = texto.replace(viejo, nuevo)
    hoja['A5'] = ArrayFormula(formula.ref, texto)
    if titulos:
        for n, titulo in enumerate(titulos, start=1):
            hoja.cell(4, n).value = titulo
    if etiqueta:
        hoja['J3'] = etiqueta
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


@tagged('post_install', '-at_install', 'safra')
class TestCombinacionesExcel(SafraCommon):
    """Revisión 10-nov: Safra mantiene la fórmula en su Excel (hoja
    «Configurador» de Panel_Track_Best_Fit_Odoo_CORREGIDO) y lo sube; Odoo
    la calcula igual que el Excel, sin traducirla a código."""

    def matriz(self, regla=None):
        regla = regla or self.combo_rule
        return {(n, f['apertura'], f['riel'], f['velcrado'])
                for a, t, n in regla._muestras(regla.telos_max) for f in regla._filas(a, t, n)}

    def subir(self, contenido, regla=None):
        (regla or self.combo_rule).write({'excel_archivo': base64.b64encode(contenido)})

    def test_lee_la_formula_del_configurador(self):
        regla = self.combo_rule
        self.assertEqual(regla.excel_ubicacion, 'Configurador!A5')
        self.assertEqual(regla.excel_entradas, {'ancho': 'K2', 'traslape': 'K3', 'telos': 'K4'})
        self.assertEqual(regla.excel_entradas_texto, 'Ancho → K2, Traslape → K3, Número de telos → K4')
        self.assertIn('FILTER', regla.excel_formula)

    def test_da_la_matriz_2_12_de_safra(self):
        self.assertEqual(self.matriz(), set(COMBINACIONES_SAFRA))
        html = str(self.combo_rule.matriz_html)
        self.assertIn('Apertura Extremos 6+6', html)
        self.assertIn('Sin combinación', html)

    def test_como_la_hoja_configurador(self):
        # Datos de entrada de la hoja: 2,50 m, traslape 8 cm, 6 telos.
        rows = self.env['safra.panel.track'].compute_configs(2.5, 0.08, 6, system=self.panel)
        self.assertEqual([(r['canales'], r['tipo_apertura'], r['ancho_telo_m'], r['condicion_especial'])
                          for r in rows], [
            (4, 'Apertura Extremos 3+3', 0.4833, 'Configuración estándar'),
            (6, 'Unilateral Derecha 0+6', 0.4833, 'Configuración estándar'),
            (6, 'Apertura Centro 3+3', 0.4833, 'Configuración estándar'),
            (6, 'Unilateral Izquierda 6+0', 0.4833, 'Configuración estándar')])
        self.assertEqual(self.combo_rule._aperturas(),
                         ['unilateral_derecha', 'unilateral_izquierda', 'centro', 'extremos'])

    def test_safra_cambia_la_formula_en_excel(self):
        # Telo mínimo de 50 cm: 2,50 m en 6 telos (48 cm) ya no da combinaciones.
        self.subir(excel_cambiado(('_xlpm.anchoMinimo,0.35', '_xlpm.anchoMinimo,0.5')))
        self.assertEqual(self.env['safra.panel.track'].compute_configs(2.5, 0.08, 6, system=self.panel), [])
        # Solo rieles de 4 y 5 canales: desaparecen las combinaciones de 6.
        self.subir(excel_cambiado(('_xlpm.cantidadRieles,3', '_xlpm.cantidadRieles,2')))
        self.assertFalse({c for c in self.matriz() if c[2] == 6})
        self.assertIn((4, 'centro', 4, False), self.matriz())

    def test_archivos_que_no_sirven(self):
        antes = self.combo_rule.excel_formula
        with self.assertRaises(UserError):
            self.subir(b'no es un excel')
        with self.assertRaises(UserError) as error:
            self.subir(excel_cambiado(('MOD(', 'XLOOKUP(')))
        self.assertIn('Odoo no calcula XLOOKUP', str(error.exception))
        with self.assertRaises(UserError) as error:
            self.subir(excel_cambiado(etiqueta='Otro dato'))
        self.assertIn('no se sabe qué dato es', str(error.exception))
        with self.assertRaises(UserError) as error:
            self.subir(excel_cambiado(titulos=['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']))
        self.assertIn('Tipo Riel', str(error.exception))
        with self.assertRaises(UserError) as error:
            self.subir(excel_cambiado(('_xlpm.anchoMaxPersiana,8', '_xlpm.anchoMaxPersiana,0')))
        self.assertIn('no da ninguna combinación', str(error.exception))
        self.assertEqual(self.combo_rule.excel_formula, antes)

    def test_sin_excel_no_hay_combinaciones_y_carga_inicial(self):
        self.combo_rule.excel_archivo = False
        self.assertFalse(self.combo_rule.excel_formula)
        self.assertEqual(self.matriz(), set())
        self.assertIn('Suba el Excel', str(self.combo_rule.matriz_html))
        self.env['safra.panel.combo.rule']._ajuste_excel_combinaciones()
        self.assertEqual(self.matriz(), set(COMBINACIONES_SAFRA))


@tagged('post_install', '-at_install', 'safra')
class TestEvaluadorExcel(SafraCommon):
    """Las funciones de Excel que calcula Odoo."""

    def calc(self, formula, **celdas):
        return excel_formula.calcular(excel_formula.leer(formula), celdas)

    def test_operaciones_y_funciones(self):
        self.assertEqual(self.calc('=1+2*3^2'), [[19.0]])
        self.assertEqual(self.calc('=ROUND(2.345,2)&" m"'), [['2.35 m']])
        self.assertEqual(self.calc('=IF(A1>2,"sí","no")', A1=3), [['sí']])
        self.assertEqual(self.calc('=_xlfn.LET(_xlpm.x,A1,_xlpm.y,_xlpm.x*2,_xlpm.y+1)', A1=4), [[9.0]])
        self.assertEqual(self.calc('=SEQUENCE(1,3)*2'), [[2.0, 4.0, 6.0]])
        self.assertEqual(self.calc('=MOD(SEQUENCE(4)-1,2)'), [[0.0], [1.0], [0.0], [1.0]])
        self.assertEqual(self.calc('=CHOOSE(SEQUENCE(1,2),SEQUENCE(2),"x")'), [[1.0, 'x'], [2.0, 'x']])
        self.assertEqual(self.calc('=_xlfn._xlws.FILTER(SEQUENCE(4),MOD(SEQUENCE(4),2)=0,"nada")'),
                         [[2.0], [4.0]])
        self.assertEqual(self.calc('=FILTER(SEQUENCE(2),SEQUENCE(2)>5,"nada")'), [['nada']])
        self.assertEqual(self.calc('=ROUNDUP(6.15,0)+ROUNDDOWN(6.85,0)+INT(-1.5)'), [[11.0]])
        self.assertEqual(self.calc('=AND(TRUE,1)+OR(FALSE,0)+NOT(0)'), [[2.0]])

    def test_errores(self):
        for formula in ('=1+', '=XLOOKUP(1,2,3)', '=1/0', '=SEQUENCE(2)+SEQUENCE(3)', '=nada+1', '=B9'):
            with self.assertRaises(excel_formula.ErrorFormula):
                self.calc(formula)
