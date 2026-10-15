from odoo import models, fields, api


class ProductClassification(models.Model):
    _name = 'product.classification'

    name = fields.Char(
        string='Nombre',
        required=True
    )
