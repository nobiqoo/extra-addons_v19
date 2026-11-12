from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    arthome_invoice_header = fields.Text(
        string='Texto del encabezado de la factura',
        help='Reemplaza el bloque central del encabezado de la factura de venta '
             'Art Home. Se respetan los saltos de línea. Si se deja vacío, se '
             'utilizan los datos de la compañía y la resolución del diario. '
             'Este texto solo cambia la presentación del PDF.',
    )
