from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    classification_id = fields.Many2one(
        comodel_name='product.classification',
        string='Clasificación'
    )
