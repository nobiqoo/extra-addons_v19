# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


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
    # Ajustes 20-oct (fila 79): el diseñador adjunta aquí el diseño final.
    safra_design_final_file = fields.Binary(
        related='safra_quote_line_id.design_final_file', readonly=False,
        string='Adjuntar diseño del diseñador')
    safra_design_final_filename = fields.Char(
        related='safra_quote_line_id.design_final_filename', readonly=False,
        string='Nombre del archivo del diseñador')

    # Reunión 15-oct (fila 74): ticket para que producción apruebe las
    # persianas «sin restricciones» del pedido.
    safra_sin_restricciones = fields.Boolean(
        string='Pedido sin restricciones', readonly=True, copy=False)
    # Sprint 1.6 (fila 128): ticket de verificación de fabricación; planta
    # lo aprueba con el mismo botón.
    safra_verificacion = fields.Boolean(
        string='Verificación de fabricación', readonly=True, copy=False)
    # Ajustes Sprint 1.6 (26-oct, fila 130): planta puede rechazar la
    # verificación con su motivo (solo el grupo que rechaza verificaciones).
    safra_rechazo_motivo = fields.Text(string='Motivo del rechazo', copy=False)
    safra_verificacion_rechazada = fields.Boolean(
        string='Verificación rechazada', readonly=True, copy=False)
    safra_produccion_aprobada = fields.Boolean(
        string='Aprobado por producción', compute='_compute_safra_produccion_aprobada')
    # Reunión 09-nov (fila 74): al aprobar la verificación, planta indica si
    # el pedido va con garantía o sin garantía, y por qué; el cliente lo ve
    # en el portal.
    safra_garantia_motivo = fields.Text(
        string='Motivo (garantía)', copy=False,
        help='Por qué el pedido va con garantía o sin garantía. Lo ve el cliente en el portal.')
    safra_garantia = fields.Selection(
        related='safra_quote_id.verificacion_garantia', string='Garantía del pedido')

    @api.depends('safra_verificacion', 'safra_quote_id.verificacion_aprobada')
    def _compute_safra_produccion_aprobada(self):
        Line = self.env['safra.quote.line'].sudo()
        for ticket in self:
            if ticket.safra_verificacion:
                ticket.safra_produccion_aprobada = ticket.safra_quote_id.verificacion_aprobada
                continue
            lines = Line.search([('production_ticket_id', '=', ticket.id)]) if ticket.id else Line
            ticket.safra_produccion_aprobada = bool(lines) and all(
                lines.mapped('sin_restricciones_aprobado'))

    def action_safra_aprobar_con_garantia(self):
        return self.with_context(safra_garantia='con').action_safra_approve_production()

    def action_safra_aprobar_sin_garantia(self):
        return self.with_context(safra_garantia='sin').action_safra_approve_production()

    def action_safra_approve_production(self):
        Line = self.env['safra.quote.line'].sudo()
        for ticket in self:
            if ticket.safra_verificacion:
                quote = ticket.safra_quote_id.sudo()
                if not quote:
                    continue
                if ticket.safra_verificacion_rechazada:
                    raise UserError('La verificación fue rechazada: el cliente debe corregir la '
                                    'cotización y se abrirá un ticket nuevo.')
                # Reunión 09-nov (fila 74): sin indicar la garantía, el pedido
                # sigue como se evaluó (sin garantía).
                garantia = self.env.context.get('safra_garantia') or 'sin'
                motivo = (ticket.safra_garantia_motivo or '').strip()
                # El motivo es obligatorio, vaya con garantía o sin garantía:
                # es lo que el cliente lee en el portal.
                if not motivo:
                    raise UserError('Escriba el Motivo (garantía) antes de aprobar: por qué el '
                                    'pedido va con garantía o sin garantía. El cliente lo verá '
                                    'en el portal.')
                quote.write({'verificacion_aprobada': True, 'verificacion_garantia': garantia,
                             'verificacion_garantia_motivo': motivo or False})
                quote._update_design_state()
                texto = 'con garantía' if garantia == 'con' else 'sin garantía'
                ticket.message_post(body=(
                    'Producción aprobó la verificación de fabricación — cotización %s: el pedido va %s%s'
                    % (quote.name or '', texto, ('. Motivo: %s' % motivo) if motivo else '.')))
                quote.message_post(body='Planta aprobó la fabricación: el pedido va %s%s' % (
                    texto, ('. Motivo: %s' % motivo) if motivo else '.'))
                continue
            lines = Line.search([('production_ticket_id', '=', ticket.id)])
            if not lines:
                continue
            lines.write({'sin_restricciones_aprobado': True})
            lines.mapped('quote_id')._update_design_state()
            ticket.message_post(body=(
                'Producción aprobó la fabricación sin restricciones (sin '
                'garantía) de las persianas %s — cotización %s.' % (
                    ', '.join(str(l.sequence // 10) for l in lines),
                    ticket.safra_quote_id.name or '')))
        return True

    def action_safra_ver_portal(self):
        """Matriz, fila 191 (reunión 28-oct): abre la cotización del ticket en
        el portal, solo para consultarla (no se puede editar desde aquí)."""
        self.ensure_one()
        if not self.safra_quote_id:
            raise UserError('El ticket no viene de una cotización del portal.')
        return {'type': 'ir.actions.act_url', 'target': 'new',
                'url': '/mis-cotizaciones/%d' % self.safra_quote_id.id}

    def action_safra_reject_verification(self):
        if not self.env.su and not self.env.user.has_group(
                'website_quotes_safra.group_safra_rechazo_verificacion'):
            raise UserError('No tiene permiso para rechazar verificaciones de fabricación.')
        for ticket in self.filtered('safra_verificacion'):
            if ticket.safra_verificacion_rechazada:
                continue
            motivo = (ticket.safra_rechazo_motivo or '').strip()
            if not motivo:
                raise UserError('Escriba el motivo del rechazo antes de rechazar.')
            quote = ticket.safra_quote_id.sudo()
            if quote.verificacion_aprobada:
                raise UserError('La verificación ya fue aprobada.')
            ticket.safra_verificacion_rechazada = True
            if quote and quote.verificacion_ticket_id == ticket:
                quote._rechazar_verificacion(motivo)
            ticket.message_post(body=(
                'Producción rechazó la verificación de fabricación — cotización %s: %s'
                % (quote.name or '', motivo)))
        return True

    def action_safra_approve_design(self):
        for ticket in self:
            line = ticket.safra_quote_line_id
            if not line:
                continue
            # Ajustes 20-oct (fila 79): se aprueba con el diseño final adjunto
            # (lo consulta la planta y lo ve el cliente en el portal).
            if not line.design_final_file:
                raise UserError('Adjunte el diseño del diseñador (imagen o PDF) antes de aprobar.')
            line.design_approved = True
            line.quote_id._update_design_state()
            ticket.message_post(body=(
                'Diseño aprobado (%.2f m² para cobro) — cotización %s.' % (
                    line.design_m2_cobro, line.quote_id.name or '')))
        return True
