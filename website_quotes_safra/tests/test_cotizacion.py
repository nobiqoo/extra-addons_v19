# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import SafraCommon


@tagged('post_install', '-at_install', 'safra')
class TestCicloCotizacion(SafraCommon):
    """Confirmación con revalidación, anulación y aprobación del diseño
    (reunión 28-sep fila 2, respuestas de Safra del 5-oct, fase 5.3)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cliente = cls.env['res.partner'].create({'name': 'Distribuidor Prueba'})

    def cotizacion(self, *lineas):
        lineas = lineas or (self.linea(),)
        return self.env['safra.quote'].create({
            'partner_id': self.cliente.id,
            'line_ids': [(0, 0, dict(l, sequence=(n + 1) * 10)) for n, l in enumerate(lineas)],
        })

    def test_confirmar_cotizacion_valida(self):
        quote = self.cotizacion()
        self.assertEqual(quote.state, 'draft')
        self.assertFalse(quote.action_confirm())
        self.assertEqual(quote.state, 'confirmed')

    def test_referencia_inactivada_bloquea(self):
        # Mejoras Sprint 1.1 (21-oct, fila 2): queda Bloqueada con el motivo
        # y se puede editar desde el portal.
        quote = self.cotizacion()
        self.tela.active = False
        resultado = quote.action_confirm()
        self.assertEqual(quote.state, 'blocked')
        self.assertIn('E20025', quote.bloqueo_motivos)
        self.assertTrue(quote.editable_portal)
        self.assertEqual(resultado['tag'], 'display_notification')
        self.assertTrue(any('E20025' in (m.body or '') for m in quote.message_ids))

    def test_regla_que_ya_no_cumple_bloquea(self):
        """Cambia la ficha del sistema después de guardar."""
        quote = self.cotizacion(self.linea(width=2.0))
        self.enrollable.tech_width_max = 1.8
        quote.action_confirm()
        self.assertEqual(quote.state, 'blocked')
        self.assertIn('OB0005', quote.bloqueo_motivos)

    def test_bloqueada_corregida_vuelve_a_borrador(self):
        quote = self.cotizacion(self.linea(color_id=self.gris.id))
        self.gris.active = False
        quote.action_confirm()
        self.assertEqual(quote.state, 'blocked')
        # Sin corregir sigue bloqueada.
        quote._desbloquear()
        self.assertEqual(quote.state, 'blocked')
        # El cliente cambia el color: vuelve a Borrador y se confirma.
        quote.line_ids.color_id = self.blanco
        quote._desbloquear()
        self.assertEqual((quote.state, quote.bloqueo_motivos), ('draft', False))
        quote.action_confirm()
        self.assertEqual(quote.state, 'confirmed')

    def test_advertencias_no_anulan(self):
        quote = self.cotizacion(self.linea(width=0.5, height=1.8))
        quote.action_confirm()
        self.assertEqual(quote.state, 'confirmed')

    def test_revisar_vigencia(self):
        vigente, vencida = self.cotizacion(), self.cotizacion(self.linea(color_id=self.gris.id))
        self.gris.active = False
        (vigente | vencida).action_revisar_vigencia()
        self.assertEqual((vigente.state, vencida.state), ('draft', 'cancelled'))

    def test_aprobacion_del_diseno(self):
        # El diseño solo va en telas estampables (y al confirmar se revisa).
        self.tela.is_printable = True
        quote = self.cotizacion(self.linea(design_print=True, custom_design='DSPRUEBA'))
        quote._update_design_state()
        self.assertEqual(quote.state, 'pending_design')
        quote.line_ids.design_approved = True
        quote._update_design_state()
        self.assertEqual(quote.state, 'design_approved')
        quote.action_confirm()
        self.assertEqual(quote.state, 'confirmed')
