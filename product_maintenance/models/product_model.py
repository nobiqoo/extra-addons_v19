# models/product_model.py
from odoo import models, fields

class ProductModel(models.Model):
    _name = 'product.model'
    _description = 'Modelo de Producto'

    name = fields.Char('Nombre del Modelo', required=True, index=True)
    codigo = fields.Char(string='Código', required=True)
    tempario_ids = fields.One2many(
        comodel_name='maintenance.tempario.model',
        inverse_name='model_id',
        string='Temparios Asociados'
    )
