# -*- cofing: utf-8 -*-

from odoo import api, models, fields


class AccountMoveline(models.Model):
    _inherit = 'account.move.line'

    work_id = fields.Many2one(
        comodel_name='sale.order.work',
        string='Obra',
        compute='_compute_work_id',
        store=True
    )

    @api.depends('move_id.work_id')
    def _compute_work_id(self):
        for record in self:
            record.work_id = record.move_id.work_id
