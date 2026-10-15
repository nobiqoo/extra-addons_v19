# models/project.py
import re
from odoo import models, _
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

class Project(models.Model):
    _inherit = "project.project"

    def _eval_with_project(self, expr, project_id):
        if not expr:
            return [] if isinstance(expr, str) or expr is None else expr

        if isinstance(expr, (list, tuple, dict)):
            return expr

        s = str(expr)
        s = re.sub(r"\bactive_id\b", str(project_id), s)
        s = re.sub(r"\bactive_ids\[0\]\b", str(project_id), s)

        try:
            return safe_eval(s, {'uid': self.env.uid})
        except Exception:
            return [] if s.strip().startswith('[') else {}

    def action_open_project_requisitions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'project_approvals_integration.action_project_requirements'
        )

        existing_domain = self._eval_with_project(action.get('domain') or '[]', self.id)
        project_domain = [('project_id', '=', self.id)]
        action['domain'] = list(Domain.AND([existing_domain or [], project_domain]))

        raw_ctx = action.get('context') or {}
        ctx = self._eval_with_project(raw_ctx, self.id) or {}
        ctx.update({
            'active_id': self.id,
            'active_model': 'project.project',
            'default_project_id': self.id,
            'search_default_project_id': self.id,
        })
        action['context'] = ctx

        action['display_name'] = _("%s - Requisiciones") % self.name
        return action

    def _get_stat_buttons(self):
        buttons = super()._get_stat_buttons()
        self.ensure_one()
        count = self.env['approval.request'].search_count([('project_id', '=', self.id)])
        buttons.append({
            'icon': 'shopping-cart',
            'text': _('Requisiciones'),
            'number': str(count),
            'action_type': 'object',
            'action': 'action_open_project_requisitions',
            'show': True,
            'sequence': 11,
        })
        return buttons
