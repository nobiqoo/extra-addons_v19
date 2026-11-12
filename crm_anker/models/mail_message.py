# -*- coding: utf-8 -*-

from odoo import fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    anker_responsible_partner_id = fields.Many2one(
        'res.partner',
        string='Encargado de la actividad',
        readonly=True,
    )
