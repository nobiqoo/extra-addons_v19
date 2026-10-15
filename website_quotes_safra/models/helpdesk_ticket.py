# -*- coding: utf-8 -*-
from odoo import fields, models


class HelpdeskTicket(models.Model):
    """Vínculo del ticket con la cotización del portal (puntos 10-11).

    Cada diseño personalizado subido en el cotizador genera un ticket para
    el área de diseño; desde la cotización se llega a sus tickets con el
    smart button y desde el ticket se ve de qué cotización/persiana viene.
    """
    _inherit = 'helpdesk.ticket'

    safra_quote_id = fields.Many2one(
        'safra.quote', string='Cotización Safra', index=True, copy=False)
    safra_quote_line_id = fields.Many2one(
        'safra.quote.line', string='Persiana', copy=False)
    # Fase 5.3: el diseñador ajusta los m² de cobro y aprueba desde el
    # ticket; con todos los diseños aprobados la cotización avanza.
    safra_design_m2 = fields.Float(
        related='safra_quote_line_id.design_m2_cobro', readonly=False,
        string='M² de cobro (diseño)')
    safra_design_approved = fields.Boolean(
        related='safra_quote_line_id.design_approved',
        string='Diseño aprobado')

    def action_safra_approve_design(self):
        for ticket in self:
            line = ticket.safra_quote_line_id
            if not line:
                continue
            line.design_approved = True
            line.quote_id._update_design_state()
            ticket.message_post(body=(
                'Diseño aprobado (%.2f m² para cobro) — cotización %s.' % (
                    line.design_m2_cobro, line.quote_id.name or '')))
        return True
