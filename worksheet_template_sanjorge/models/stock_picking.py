# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def check_quality(self):
        self.env.context = dict(self.env.context, from_picking=True)
        return super(StockPicking, self).check_quality()