from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    webflor_product_code = fields.Char(
        string='Id Producto WebFlor',
        help='Identificador del producto en el catálogo de WebFlor. '
             'Relaciona el producto de WebFlor con su homólogo en Odoo, '
             'facilitando la integración y sincronización de información.',
    )
    webflor_referente = fields.Char(
        string='Referente',
        help='Clasificación o agrupación de la línea según la categoría del '
             'producto, utilizada para análisis, reportería e integración.',
    )
