# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    note_sale_to_picking = fields.Boolean(
        string='Sales order note in the delivery order',
        help='Allows you to keep the sales order note to the delivery order note.'
    )

    picking_analytic = fields.Boolean(
        string='Transfer Analytic',
        help='Create analytical lines on the transfer.',
        default=True,
    )

    validate_incoming_receptions = fields.Boolean(
        string='Validate Incoming Receptions by Users',
        help='Users will need permissions to validate incoming receptions. This setting requires to assign users to warehouses.',
        default=False,
    )
