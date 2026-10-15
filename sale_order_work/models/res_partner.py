# -*- cofing: utf-8 -*-

from odoo import api, models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    work_ids = fields.Many2many(
        'sale.order.work',
        'partner_work_rel',
        'partner_id', 'work_id',
        string='Obra'
    )
