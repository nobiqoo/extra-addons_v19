# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields


class ClassLocation(models.Model):

    _name = 'wk.class.location'
    _inherit = "wk.company.visibility.mixin"
    _description = 'Class Location'

    name = fields.Char('Name', required=True)
    sequence = fields.Integer(default=1)
    company_id = fields.Many2one(
        'res.company', string="School", default=lambda self: self.env.company, required=True)
    active = fields.Boolean(
        'Active', default=True,
        help="By unchecking the active field, you may hide an meeting place you will not use.")
