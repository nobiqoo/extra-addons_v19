# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    taxes_id = fields.Many2many(
        compute='_compute_taxes_id',
        inverse='_inverse_taxes_id',
        relation='product_taxes_rel',
        column1='prod_id',
        column2='tax_id',
        store=True
    )
    supplier_taxes_id = fields.Many2many(
        compute='_compute_taxes_id',
        inverse='_inverse_taxes_id',
        relation='product_supplier_taxes_rel',
        column1='prod_id',
        column2='tax_id',
        store=True
    )

    @api.depends('categ_id.taxes_categ_id', 'categ_id.supplier_taxes_categ_id')
    def _compute_taxes_id(self):
        for template in self.filtered(lambda t: t.categ_id):
            if template._origin.id is not False:
                # Sales taxes
                self._cr.execute('DELETE FROM product_taxes_rel WHERE prod_id = {prod_id}'.format(
                    prod_id=template._origin.id))
                self._cr.execute('SELECT tax_id FROM category_taxes_rel WHERE categ_id = {categ_id}'.format(
                    categ_id=template.categ_id.id))
                result_sale_taxes = self._cr.fetchall()
                for tax in result_sale_taxes:
                    self._cr.execute('INSERT INTO product_taxes_rel(prod_id, tax_id) VALUES ({prod_id},{tax_id})'.format(
                        prod_id=template._origin.id,
                        tax_id=tax[0]
                    ))
                # Purchase taxes
                self._cr.execute('DELETE FROM product_supplier_taxes_rel WHERE prod_id = {prod_id}'.format(
                    prod_id=template._origin.id))
                self._cr.execute('SELECT tax_id FROM category_supplier_taxes_rel WHERE categ_id = {categ_id}'.format(
                    categ_id=template.categ_id.id))
                result_suppler_taxes = self._cr.fetchall()
                for tax in result_suppler_taxes:
                    self._cr.execute('INSERT INTO product_supplier_taxes_rel(prod_id, tax_id) VALUES ({prod_id},{tax_id})'.format(
                        prod_id=template._origin.id,
                        tax_id=tax[0]
                    ))

    def force_update_taxes_from_category(self):
        for template in self:
            template._compute_taxes_id()

    def _inverse_taxes_id(self):
        for template in self:
            template.inverse_taxes_id()

    def inverse_taxes_id(self):
        self.ensure_one()
        # TODO create a wizard o note
        return True

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for record in res:
            record._compute_taxes_id()
        return res
