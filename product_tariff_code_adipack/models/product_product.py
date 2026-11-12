from odoo import api, models
from odoo.fields import Domain


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _search_display_name(self, operator, value):
        # Allow finding the product by its old reference (e.g. on sale order lines)
        domain = super()._search_display_name(operator, value)
        old_reference_domain = [('product_tmpl_id.old_reference', operator, value)]
        if operator in Domain.NEGATIVE_OPERATORS:
            return Domain.AND([domain, old_reference_domain])
        return Domain.OR([domain, old_reference_domain])

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        # Complete the standard results with the products matching the old reference
        result = super().name_search(name, domain, operator, limit)
        if not name or operator in Domain.NEGATIVE_OPERATORS or (limit and len(result) >= limit):
            return result
        found_ids = [product_id for product_id, _name in result]
        old_reference_domain = Domain(domain or Domain.TRUE) \
            & Domain('product_tmpl_id.old_reference', operator, name) \
            & Domain('id', 'not in', found_ids)
        products = self.search_fetch(old_reference_domain, ['display_name'], limit=limit and limit - len(result))
        return result + [(product.id, product.display_name) for product in products.sudo()]
