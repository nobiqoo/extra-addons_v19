from odoo import _, api, fields, models, tools



class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    tariff_code = fields.Char(string="Tariff code")