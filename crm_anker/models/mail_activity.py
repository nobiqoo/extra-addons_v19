# -*- coding: utf-8 -*-

from odoo import fields, models


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    anker_responsible_partner_id = fields.Many2one(
        'res.partner',
        string='Encargado de la actividad',
        domain=[('is_company', '=', False)],
    )
