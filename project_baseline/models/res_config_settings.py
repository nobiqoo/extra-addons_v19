# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    project_task_income_expense = fields.Boolean(
        'Income and expense in project task',
        related='company_id.project_task_income_expense',
        readonly=False
    )
