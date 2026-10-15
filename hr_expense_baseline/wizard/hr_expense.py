# -*- coding: utf-8

from odoo import _, api, fields, models


class HrExpenseAdvanceSetting(models.TransientModel):
    _name = 'hr.expense.advance.setting'
    _description = 'HR Expense Advance Setting'

    days_for_due = fields.Integer(
        string='Days for Due Date',
        default=None,
        required=True,
        help='Number of days for the due date after the request date.',
    )

    def set_days_for_due(self):
        self.ensure_one()
        self.env['ir.config_parameter'].sudo().set_param(
            'hr_expense_baseline.days_for_due', self.days_for_due
        )
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def default_get(self, fields_list):
        defaults = super(HrExpenseAdvanceSetting,
                         self).default_get(fields_list)
        days_for_due = (
            self.env['ir.config_parameter']
            .sudo()
            .get_param('hr_expense_baseline.days_for_due', default=None)
        )
        if days_for_due:
            defaults['days_for_due'] = int(days_for_due)
        return defaults
