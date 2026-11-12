from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    arthome_split_invoice_lots = fields.Boolean(
        string='Una línea por rollo en la factura electrónica',
        help='Separa el detalle impreso por lote y muestra la cantidad entregada de '
             'cada rollo. Sin marcar, conserva los lotes agrupados. No modifica las '
             'líneas contables. Si las cantidades de entrega no coinciden con las '
             'facturadas, conserva la línea agrupada para no asignar cantidades '
             'incorrectas a los lotes.',
    )
