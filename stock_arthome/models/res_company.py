# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    insurable_value_percentage = fields.Float(
        string='Insurable Value Percentage',
        default=70.0,
        help='Percentage of the sale order net price applied to the transfer quantities '
             'to compute the insurable value of the transfer.',
    )

    _insurable_value_percentage_range = models.Constraint(
        'CHECK(insurable_value_percentage >= 0 AND insurable_value_percentage <= 100)',
        'The insurable value percentage must be between 0 and 100.',
    )
