
# -*- coding: utf-8 -*-

from odoo import api, models, fields
from datetime import date
from odoo.exceptions import ValidationError


class ProductTemplateMaintenanceProduct(models.Model):
    _name = 'product.template.maintenance.product'
    _description = 'Piezas de Mantenimiento'

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto',
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string="Unidad de Medida",
        domain="[('id', 'in', allowed_uom_ids)]"
    )
    allowed_uom_ids = fields.Many2many(
        comodel_name='uom.uom',
        compute='_compute_allowed_uom_ids'
    )
    product_uom_qty = fields.Float(
        string='Cantidad'
    )
    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Producto Template'
    )
    repair_id = fields.Many2one(
        comodel_name='repair.order',
        string='Reparación'
    )
    product_maintenance_id = fields.Many2one(
        comodel_name='product.maintenance',
        string='Producto de Mantenimiento'
    )
    analytic_distribution = fields.Json(
        string='Analytic Distribution'
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic'),
    )

    @api.depends('product_id')
    def _compute_allowed_uom_ids(self):
        for record in self:
            record.allowed_uom_ids = record.product_id.uom_id | record.product_id.uom_ids

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('analytic_distribution'):
                continue
            repair_id = vals.get('repair_id')
            if repair_id:
                repair = self.env['repair.order'].browse(repair_id)
                distribution = repair._get_account_analytic_distribution()
                if distribution:
                    vals['analytic_distribution'] = distribution
        return super().create(vals_list)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for record in self:
            record.product_uom_id = False
            if record.product_id:
                record.product_uom_id = record.product_id.uom_id

    @api.constrains('product_uom_qty')
    def _check_product_uom_qty(self):
        for record in self:
            if record.product_uom_qty <= 0:
                raise ValidationError('La cantidad debe ser superior a cero.')
