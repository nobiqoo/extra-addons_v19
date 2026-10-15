# -*- coding: utf-8 -*-

from odoo import fields, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    is_fixed_time = fields.Boolean('Tiempo fijo',
                                default=False)