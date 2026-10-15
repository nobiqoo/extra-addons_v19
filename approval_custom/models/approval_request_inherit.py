from odoo import models, api


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def _get_project_analytic_account(self):
        self.ensure_one()
        if 'project_id' not in self._fields:
            return False

        project = self.project_id
        if not project or 'account_id' not in project._fields:
            return False

        return project.account_id

    @api.onchange('project_id')
    def _onchange_project_id_sync_lines(self):
        for req in self:
            aa = req._get_project_analytic_account()
            if not aa:
                continue

            for line in req.product_line_ids:
                if not line.analytic_distribution:
                    line.analytic_distribution = {aa.id: 100.0}
                if not line.analytic_account_id:
                    line.analytic_account_id = aa.id

    def write(self, vals):
        res = super().write(vals)

        if 'project_id' in vals:
            for req in self:
                aa = req._get_project_analytic_account()
                if not aa:
                    continue

                for line in req.product_line_ids:
                    update_vals = {}
                    if not line.analytic_distribution:
                        update_vals['analytic_distribution'] = {aa.id: 100.0}
                    if not line.analytic_account_id:
                        update_vals['analytic_account_id'] = aa.id
                    if update_vals:
                        line.write(update_vals)

        return res
