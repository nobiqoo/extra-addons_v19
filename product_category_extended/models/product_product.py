# -*- coding: utf-8 -*-

from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    fracaweb_reference = fields.Char(string="Fracaweb reference")
    sigo_reference = fields.Char(string="Secuence Sigo")
    mrp_bom_since_tmpl = fields.Many2one(comodel_name='mrp.bom',
                                         string="Mrp bom automatically created",
                                         )

    def update_default_code_to_product(self):
        tmpl_code = self.product_tmpl_id.default_code
        if not self.product_tmpl_id.skip_automatic_reference and self.env.company.apply_product_reference:
            default_code = self.get_default_code_reference()
            self.update({'default_code': default_code})
        self.product_tmpl_id.default_code = tmpl_code

    def get_default_code_reference(self):
        categ = self.product_tmpl_id.categ_id
        cat_reference = ''
        if categ:
            categs = []
            while len(categ) > 0:
                if categ.reference != False:
                    categs.insert(0, categ.reference or '')
                categ = categ.parent_id

            cat_reference = cat_reference + ''.join(categs)
        tmlp_code = cat_reference + '/' + self.product_tmpl_id.secuence_reference
        attributes = [
            line.product_attribute_value_id for line in self.product_template_attribute_value_ids]
        attribute_list = []
        for attribute in attributes:
            attribute_list.append(attribute.number or '')
        reference_code = tmlp_code + ''.join(attribute_list)
        return reference_code
