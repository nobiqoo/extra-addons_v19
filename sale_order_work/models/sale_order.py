# -*- cofing: utf-8 -*-

from odoo import api, models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    work_id = fields.Many2one(
        comodel_name='sale.order.work',
        string='Obra'
    )

    def _prepare_invoice(self):
        res = super()._prepare_invoice()
        if self.work_id:
            res['work_id'] = self.work_id.id
        return res
