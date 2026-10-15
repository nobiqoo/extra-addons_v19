# -*- cofing: utf-8 -*-

from odoo import api, models, fields


class SaleOrderWork(models.Model):
    _name = 'sale.order.work'
    _description = 'Obras Ventas'

    name = fields.Char(
        string='Nombre'
    )
    description = fields.Char(
        string='Descripción'
    )
    partner_ids = fields.Many2many(
        'res.partner',
        'partner_work_rel',
        'work_id', 'partner_id',
        string='Terceros'
    )
