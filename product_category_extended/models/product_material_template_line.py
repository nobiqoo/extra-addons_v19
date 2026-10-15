# -*- coding: utf-8 -*-

from odoo import api, models, fields


class ProductMaterialTemplateLine(models.Model):
    _name = 'product.material.template.line'
    _description = 'Product Material Template Line'

    product_tmpl_id = fields.Many2one(
        'product.template', string="Product", required=True)
    uom_id = fields.Many2one(
        'uom.uom', string="Unit of measure", related="product_tmpl_id.uom_id")
    uom_qty = fields.Float(string="Quantity", default=0, required=True)
    tmpl_id = fields.Many2one('product.template', string="Template")

    def write(self, vals):
        for record in self:
            uom_qty = uom_qty = vals['uom_qty'] if 'uom_qty' in vals else self.uom_qty
            if 'product_tmpl_id' in vals:
                tmpl = self.env['product.template'].browse(
                    vals['product_tmpl_id'])
            else:
                tmpl = record.product_tmpl_id
            vals['uom_qty'] = tmpl.uom_id._compute_quantity(
                uom_qty, tmpl.uom_id
            )
        return super(ProductMaterialTemplateLine, self).write(vals)

    @api.model_create_multi
    def create(self, vals):
        res = super(ProductMaterialTemplateLine, self).create(vals)
        res.uom_qty = res.uom_id._compute_quantity(
            res.uom_qty, res.product_tmpl_id.uom_id
        )
        return res
