# models/product_model.py
from odoo import models, fields

class ProductModel(models.Model):
    _name = 'product.plate'
    _description = 'placa de Producto'

    name = fields.Char('Placa del Modelo', index=True)
    codigo = fields.Char(string='Código')
