# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    note_sale_to_picking = fields.Boolean(
        related='company_id.note_sale_to_picking',
        readonly=False
    )

    picking_analytic = fields.Boolean(
        related='company_id.picking_analytic',
        readonly=False
    )

    validate_incoming_receptions = fields.Boolean(
        related='company_id.validate_incoming_receptions',
        readonly=False
    )
