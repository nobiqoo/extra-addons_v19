# -*- coding: utf-8 -*-

from odoo import fields, models, _


class HelpdeskTicketImageSm(models.Model):
    _name = 'helpdesk.ticket.image.sm'
    _description = 'Images for helpdesk ticket'

    name = fields.Char('Name')
    image = fields.Image('Image')
    ticket_id = fields.Many2one('helpdesk.ticket', 'Ticket')

    def view_image(self):
        print('Hallo')
        return {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'helpdesk.ticket.image.sm',
            'views': [(self.env.ref('helpdesk_extended.helpdesk_ticket_image_sm_view_form').id, 'form')],
            'res_id': self.id,
            'target': 'new',
            'context': {},
        }
