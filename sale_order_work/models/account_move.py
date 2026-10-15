# -*- cofing: utf-8 -*-

from odoo import api, models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    work_id = fields.Many2one(
        comodel_name='sale.order.work',
        string='Obra'
    )
