from odoo import models, fields, api


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    classification_id = fields.Many2one(
        comodel_name='product.classification',
        string='Clasificación',
        compute='_compute_classification_id',
        store=True
    )

    @api.depends('product_id.classification_id')
    def _compute_classification_id(self):
        for record in self:
            record.classification_id = record.product_id.classification_id
