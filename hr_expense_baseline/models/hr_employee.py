# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# TODO: OK

from odoo import fields, models, api


class Employee(models.Model):
    _inherit = 'hr.employee'

    approvers_ids = fields.Many2many(
        comodel_name='res.users',
        string='Advance Approvers',
        help='Users who can approve the advances for this employee.'
    )
