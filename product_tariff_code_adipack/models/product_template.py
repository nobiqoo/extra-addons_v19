from odoo import _, api, fields, models, tools



class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    tariff_code = fields.Char(string="Tariff code")
    old_reference = fields.Char(string="Old reference", index='trigram',
                                help="Reference of the previous version of this product, replaced by the current one.")
