# -*- cofing: utf-8 -*-

from odoo import models, fields


class AccountReport(models.Model):
    _inherit = 'account.report'

    filter_work = fields.Boolean(
        string="Obras",
        compute=lambda x: x._compute_report_option_filter('filter_work'), readonly=False, store=True, depends=['root_report_id', 'section_main_report_ids'],
    )
