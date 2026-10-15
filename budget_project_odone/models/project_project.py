from odoo import models, _
import calendar
from datetime import date

class Project(models.Model):
    _inherit = 'project.project'

    def action_open_budget_analytic_account(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget for analytical account of the project'),
            'res_model': 'crossovered.budget.lines',
            'view_mode': 'list,form',
            'domain': [('analytic_account_id', '=', self.account_id.id)],
            'context': {
                'default_analytic_account_id': self.account_id.id,
                    'create': False,
            'edit': False,
            'delete': False,
            },
        }

    def action_account_budget_elite_create_budget(self):
        self.ensure_one()
        today = date.today()
        date_from = today.replace(day=1)
        date_to = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create budget'),
            'res_model': 'crossovered.budget',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_analytic_account_id': self.account_id.id,
                'default_date_from': date_from,
                'default_date_to': date_to,
            },
        }
    
    def _get_stat_buttons(self):
        buttons = super()._get_stat_buttons()
        self.ensure_one()
        count = self.env['crossovered.budget.lines'].search_count([('analytic_account_id', '=', self.account_id.id)])
        buttons.append({
            'icon': 'line-chart',
            'text': _('Budget by budget situation'),
            'number': str(count),
            'action_type': 'object',
            'action': 'action_open_budget_analytic_account',
            'show': True,
            'sequence': 12,
        })
        buttons.append({
            'icon': 'plus-circle',
            'text': _('Create budget'),
            'number': '',
            'action_type': 'object',
            'action': 'action_account_budget_elite_create_budget',
            'show': bool(self.account_id),
            'sequence': 13,
        })
        return buttons
