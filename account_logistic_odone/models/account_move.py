# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


selection_due = [
    ('000', '0'),
    ('030', '1 - 30'),
    ('060', '31 - 60'),
    ('090', '61 - 90'),
    ('120', '91 - 120'),
    ('180', '121 - 180'),
    ('360', '181 - 360'),
    ('inf', 'Mayor'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    # consol
    city = fields.Char(string='City.')
    position = fields.Char(string='Position')
    hbl = fields.Char(string='HBL')
    container_number = fields.Char(string='Container number')
    origin = fields.Char(string='Origin')
    destination = fields.Char(string='Destination')
    volume = fields.Char(string='Volume')
    customer_order = fields.Char(string='Customer order')
    motor_ship = fields.Char(string='Motor ship')
    text_weight = fields.Char('Weight')
    networks_ids = fields.Many2many(
        'res.partner.network',
        string="Networks",
        related='partner_id.networks_ids'
    )

    def action_post(self):
        for record in self:
            for line in record.line_ids:
                line.position = record.position
        return super(AccountMove, self).action_post()
