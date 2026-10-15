# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    product_id = fields.Many2one('product.product', string="Late Fee Element", domain="[('is_fee_element','=',True)]")
    scholarship_product_id = fields.Many2one('product.product', string="Scholarship Element", domain="[('is_fee_element','=',True)]")
    no_of_days = fields.Integer(string="Days to confirm the fee slip before")
    not_of_return_days = fields.Integer(string="Days to keep the book")
    fine_policy  = fields.Float(string="Fine")
    max_book_allowed = fields.Integer(string="Max. book allowed", default="5")
    show_service_hours = fields.Boolean(
        string="Show Service Hours",
        config_parameter='wk_school_management.show_service_hours' 
    )

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrDefault = self.env['ir.default'].sudo()

        IrDefault.set('res.config.settings', 'product_id', self.product_id.id)
        IrDefault.set('res.config.settings', 'no_of_days', self.no_of_days)
        IrDefault.set('res.config.settings',
                      'scholarship_product_id', self.scholarship_product_id.id)
        IrDefault.set('res.config.settings',
                      'not_of_return_days', self.not_of_return_days)
        IrDefault.set('res.config.settings',
                      'fine_policy', self.fine_policy)
        IrDefault.set('res.config.settings',
                      'max_book_allowed', self.max_book_allowed)
        IrDefault.set('res.config.settings',
                      'show_service_hours', True)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IrDefaultGet = self.env['ir.default'].sudo()._get
        product_id = IrDefaultGet('res.config.settings', 'product_id')
        scholarship_product_id = IrDefaultGet('res.config.settings', 'scholarship_product_id')
        no_of_days = IrDefaultGet('res.config.settings', 'no_of_days') or 10
        not_of_return_days = IrDefaultGet('res.config.settings', 'not_of_return_days') or 5
        fine_policy = IrDefaultGet('res.config.settings', 'fine_policy') or 5
        max_book_allowed = IrDefaultGet('res.config.settings', 'max_book_allowed') or 5

        res.update(
            scholarship_product_id=scholarship_product_id,
            product_id=product_id,
            no_of_days=no_of_days,
            not_of_return_days=not_of_return_days,
            fine_policy=fine_policy,
            max_book_allowed=max_book_allowed,)
        return res
