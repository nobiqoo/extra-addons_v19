# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon
from ..models import safra_reglas_17 as R17


@tagged('post_install', '-at_install', 'safra')
class TestPruebaFormulas(SafraCommon):
    """Probar fórmulas (03-nov): Ajustes › Cotizador Safra muestra, para una
    persiana real, el valor de cada variable y el result de cada fórmula,
    con lo escrito en pantalla aunque no se haya guardado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().search([('key', 'in', list(R17.FORMULAS_TUBO)
                                                       + list(R17.FORMULAS_CORTE_CORTINA))]).unlink()
        cls.cortina = cls._sistema('ZT59', 'PRUEBA CORTINA FORMULAS',
                                   ['width', 'height', 'quantity', 'location', 'fabric_id', 'color_id'],
                                   (0.30, 11.8, 0.30, 5.0))
        cls.cortina.calculo_corte = 'cortina'
        cls.enrollable.calculo_corte = 'persiana'
        cls.tela.system_ids = [(4, cls.cortina.id)]
        cliente = cls.env['res.partner'].create({'name': 'Distribuidor Prueba'})
        cls.quote = cls.env['safra.quote'].create({'partner_id': cliente.id, 'line_ids': [
            (0, 0, cls.linea(cls, fabric_id=cls.tela_pesada.id, color_id=cls.pesada.id, sequence=10)),
            (0, 0, cls.linea(cls, system_id=cls.cortina.id, width=2.0, height=2.6, sequence=20)),
        ]})
        cls.persiana, cls.cortina_linea = cls.quote.line_ids.sorted('sequence')

    def resultado(self, line, **formulas):
        Wizard = self.env['safra.formula.prueba']
        if formulas:
            Wizard = Wizard.with_context(safra_formulas_prueba=formulas)
        return str(Wizard.create({'line_id': line.id}).resultado)

    def test_tubo_variables_y_result(self):
        # R8 manual: espacio 60, diámetro 40, carga 2000; tela 300 g/m², 0,5 mm.
        html = self.resultado(self.persiana)
        self.assertIn('Tubo de esta persiana: <b>R8</b>', html)
        self.assertIn('<code>carga_maxima</code> = 2000.0', html)
        self.assertIn('<b>10.0531</b>', html)   # alto por espacio
        self.assertIn('<b>4.4444</b>', html)    # alto por carga
        self.assertIn('<b>810.0</b>', html)     # peso 1,5 × 1,8 × 300
        self.assertNotIn('Carga máxima del motor', html)
        self.assertIn('Cuadro del «?»', html)

    def test_tubo_formula_escrita_sin_guardar(self):
        html = self.resultado(self.persiana, **{
            'safra.formula.tubo_peso_total': 'result = ancho * alto * peso_tela * 2'})
        self.assertIn('<b>1620.0</b>', html)
        # Lo guardado no cambió.
        self.assertIn('<b>810.0</b>', self.resultado(self.persiana))

    def test_error_y_raise_se_muestran(self):
        html = self.resultado(self.persiana, **{
            'safra.formula.tubo_peso_total': 'result = ancho * (alto'})
        self.assertIn('Error:', html)
        html = self.resultado(self.persiana, **{
            'safra.formula.tubo_alto_carga': "raise Exception('peso tela %s' % peso_tela)"})
        self.assertIn('Error: peso tela 300.0', html)

    def test_cortina_formulas_del_corte(self):
        # Rollo 2,50: alto 2,60 no va normal, sí con bajo falso (≤ 2,50 + 0,12).
        html = self.resultado(self.cortina_linea)
        self.assertIn('Cortinas: fórmulas del corte', html)
        self.assertIn('Alto máximo con un dobladillo (consumo 0.21)', html)
        self.assertIn('<b>False (no)</b>', html)
        self.assertIn('<b>True (sí)</b>', html)
        self.assertIn('Corte de esta cortina: <b>Bajo falso</b>', html)
        # Solo las variables del código, no las palabras de los comentarios.
        # (el comentario de la fórmula del bajo falso dice «ancho del rollo»).
        bajo_falso = html.split('Cortina con bajo falso si…')[1].split('</tr>')[0]
        self.assertIn('<code>ancho_rollo</code> = 2.5', bajo_falso)
        self.assertNotIn('<code>ancho</code>', bajo_falso)
        html = self.resultado(self.cortina_linea, **{'safra.formula.cortina_bajo_falso': 'result = False'})
        self.assertIn('<b>No se puede fabricar</b>', html)

    def test_boton_de_ajustes_lleva_lo_escrito(self):
        settings = self.env['res.config.settings'].create({
            'safra_formula_tubo_peso_total': 'result = 1'})
        accion = settings.action_probar_formulas()
        formulas = accion['context']['safra_formulas_prueba']
        self.assertEqual(formulas['safra.formula.tubo_peso_total'], 'result = 1')
        self.assertEqual(set(formulas), set(R17.FORMULAS_TUBO) | set(R17.FORMULAS_CORTE_CORTINA))

    def test_nombre_de_la_persiana(self):
        self.assertEqual(self.persiana.display_name,
                         '%s · Sala · PRUEBA ENROLLABLE · 1.5 × 1.8' % self.quote.name)
