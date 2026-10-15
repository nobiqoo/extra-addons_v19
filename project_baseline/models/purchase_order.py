# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    bl_task_id = fields.Many2one('project.task',
                                 'Project task',
                                 copy=False)
    project_task_income_expense = fields.Boolean(
        'Income and expense in project task',
        related='company_id.project_task_income_expense'
    )
