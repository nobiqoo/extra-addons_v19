# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ProductCategory(models.Model):
    _inherit = 'product.category'

    taxes_categ_id = fields.Many2many(
        'account.tax',
        'category_taxes_rel',
        'categ_id',
        'tax_id',
        string='Customer Taxes',
        help='Default taxes used when selling the product.',
        domain=[('type_tax_use', '=', 'sale')],
        default=lambda self: self.env.company.account_sale_tax_id
    )
    supplier_taxes_categ_id = fields.Many2many(
        'account.tax',
        'category_supplier_taxes_rel',
        'categ_id',
        'tax_id',
        string='Vendor Taxes',
        help='Default taxes used when buying the product.',
        domain=[('type_tax_use', '=', 'purchase')],
        default=lambda self: self.env.company.account_purchase_tax_id
    )

    def action_recompute_product_taxes(self):
        templates = self.env['product.template'].search([('categ_id', 'in', self.ids)])
        count = len(templates)

        if count:
            templates.force_update_taxes_from_category()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Recalculo de Impuestos"),
                'message': (_("Se actualizaron %s productos.") % count) if count else _("No se encontraron productos."),
                'type': 'success' if count else 'warning',
                'sticky': False,
            },
        }
