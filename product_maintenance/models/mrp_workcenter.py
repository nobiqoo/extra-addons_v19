# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    product_maintenance_ids = fields.One2many(
        comodel_name='product.maintenance',
        inverse_name='workcenter_id',
        string='Productos de Mantenimiento',
    )
    use_product_maintenance_in_workcenters = fields.Boolean(
        related='company_id.use_product_maintenance_in_workcenters'
    )
