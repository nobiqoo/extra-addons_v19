# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .product_template import RISK_CLASS_SELECTION


class StockMove(models.Model):
    _inherit = 'stock.move'

    brand_id = fields.Many2one(
        comodel_name='product.brand',
        string='Brand',
        compute='_compute_reception_act_data',
        store=True,
        readonly=False,
    )
    commercial_presentation = fields.Char(
        string='Commercial Presentation',
        compute='_compute_reception_act_data',
        store=True,
        readonly=False,
    )
    sanitary_registration = fields.Char(
        string='Sanitary Registration',
        compute='_compute_reception_act_data',
        store=True,
        readonly=False,
    )
    shelf_life = fields.Char(
        string='Shelf Life',
        compute='_compute_reception_act_data',
        store=True,
        readonly=False,
    )
    risk_class = fields.Selection(
        selection=RISK_CLASS_SELECTION,
        string='Risk Class',
        compute='_compute_reception_act_data',
        store=True,
        readonly=False,
    )

    @api.depends('product_id')
    def _compute_reception_act_data(self):
        for move in self:
            template = move.product_id.product_tmpl_id
            move.brand_id = template.product_brand_id
            move.commercial_presentation = template.commercial_presentation
            move.sanitary_registration = template.sanitary_registration
            move.shelf_life = template.shelf_life
            move.risk_class = template.risk_class
