
class ProductIdOnchangeMixin:
    def _get_product_ids(self, pricelist):
        product_ids = [
            item.product_id.id for item in pricelist.item_ids if item.product_id
        ]
        product_ids.extend([
            variant.id for item in pricelist.item_ids if item.product_tmpl_id
            for variant in item.product_tmpl_id.product_variant_ids
        ])
        return product_ids

    def _onchange_product_id_common(self, order):
        if order.partner_id and order.partner_id.property_product_pricelist:
            pricelist = order.partner_id.property_product_pricelist
            product_ids = self._get_product_ids(pricelist)
            return {'domain': {'product_id': [('id', 'in', product_ids)]}}
