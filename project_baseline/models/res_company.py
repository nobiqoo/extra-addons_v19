# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    project_task_income_expense = fields.Boolean(
        'Income and expense in project task',
        help='Allows to manage income and expenses from project tasks.'
    )
