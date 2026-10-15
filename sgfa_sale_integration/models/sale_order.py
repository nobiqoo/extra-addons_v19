from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    orden_sgfa = fields.Char(
        string='Orden SGFA',
        copy=False,
        index=True,
        readonly=True,
        tracking=True,
        help=(
            'Identificador único de la Orden de Servicio creada en SGFA. '
            'Se diligencia automáticamente a través del punto de '
            'integración SGFA -> Odoo y se utiliza exclusivamente para '
            'trazabilidad entre ambos sistemas. No debe modificarse '
            'manualmente ni se tiene en cuenta en cálculos o '
            'validaciones comerciales.'
        ),
    )
