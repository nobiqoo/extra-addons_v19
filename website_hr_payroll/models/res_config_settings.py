# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    leave_notifier_website = fields.Boolean(
        related='company_id.leave_notifier_website',
        readonly=False,
    )
    leave_notifier_website_employee = fields.Boolean(
        related='company_id.leave_notifier_website_employee',
        readonly=False,
    )
    leave_notifier_payroll_users_website = fields.Boolean(
        related='company_id.leave_notifier_payroll_users_website',
        readonly=False,
    )
    payroll_users_ids = fields.Many2many(
        related='company_id.payroll_users_ids',
        readonly=False,
    )
    range_years_in_website = fields.Integer(
        string='Rango de años en sitio web',
        help='Rango de años mostrados en el portal de empleados.',
        config_parameter='website_hr_payroll.range_years_in_website',
        default=2,
    )
