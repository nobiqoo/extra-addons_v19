from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    margin_percentage = fields.Float(
        string='Margen de utilidad (%)',
        help=(
            'Margen minimo de utilidad permitido para ventas. '
            'Si se deja en cero, no se aplicara la restriccion.'
        ),
    )
    sku = fields.Char(string='SKU')

    @api.constrains('margin_percentage')
    def _check_margin_percentage_positive(self):
        for product in self:
            if product.margin_percentage < 0:
                raise ValidationError(_('El margen de utilidad no puede ser negativo.'))
