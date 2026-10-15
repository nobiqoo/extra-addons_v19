# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    guardian_id = fields.Many2one('res.partner', string='Responsable o Acudiente')
    guardian_phone = fields.Char(string='Teléfono del Responsable o Acudiente')

    @api.onchange('guardian_id')
    def _onchange_guardian_id(self):
        for ticket in self:
            if ticket.guardian_id:
                ticket.guardian_phone = ticket.guardian_id.phone
