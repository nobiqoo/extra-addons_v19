# -*- coding: utf-8 -*-
"""Código de beneficio/cupón como botón propio de la Inscripción (ronda de
ajustes post-prueba), análogo a los botones "Coupon Code"/"Reward" de Ventas
(sale_loyalty) -pero sobre el motor ligero wk.fee.benefit, no el motor
completo de sale_loyalty (ver fee_benefit.py).

Antes vivía como un simple Char ("codigo_beneficio") dentro del wizard
"Generar recibos de tarifas" (wk.fee.generate.wizard); ahora se aplica en
cualquier momento, directamente desde la pestaña "Resumen de tarifas" de la
Inscripción, sobre el recibo de tarifa más reciente que todavía no tenga
factura -la misma condición que ya exigía wk.fee.benefit.apply_benefit(). Si
todavía no existe ese recibo, el código se deja pendiente en la propia
Inscripción (student_enrollment.py::codigo_beneficio_pendiente) y
fee_slip_wizard.py lo aplica en cuanto genera el recibo.
"""
from odoo import fields, models, _


class FeeBenefitWizard(models.TransientModel):
    _name = 'wk.fee.benefit.wizard'
    _description = 'Aplicar beneficio/cupón a un recibo de tarifa'

    enrollment_id = fields.Many2one(
        'student.enrollment', string='Inscripción', required=True,
        default=lambda self: self.env.context.get('active_id'))
    codigo = fields.Char(string='Código de beneficio / cupón', required=True)

    def _get_fee_slip(self):
        self.ensure_one()
        return self.enrollment_id.fee_slip_ids.filtered(
            lambda slip: slip.state != 'cancel' and not slip.invoice_ids
        ).sorted('id', reverse=True)[:1]

    def action_apply(self):
        self.ensure_one()
        fee_slip = self._get_fee_slip()
        if fee_slip:
            self.env['wk.fee.benefit'].apply_benefit(fee_slip, self.codigo)
            return True

        # Todavía no hay ningún recibo de tarifa sin facturar (p. ej. antes
        # de "Generar recibos de tarifas"): se guarda el código para que
        # fee_slip_wizard.py lo aplique automáticamente en cuanto genere el
        # recibo, sin importar si es pago único o por cuotas.
        self.enrollment_id.codigo_beneficio_pendiente = self.codigo
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Código guardado'),
                'message': _(
                    'Todavía no hay un recibo de tarifa pendiente de '
                    'facturar. El código se aplicará automáticamente al '
                    'generar el próximo recibo.'),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
