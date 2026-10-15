# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_technician = fields.Boolean('Technician', default=False)
    tech_city_id = fields.Many2one('res.city', 'Technician city')
