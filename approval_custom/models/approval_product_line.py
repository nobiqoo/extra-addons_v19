from odoo import models, fields, api


class ApprovalProductLine(models.Model):
    _name = 'approval.product.line'
    _inherit = ['approval.product.line', 'analytic.mixin']

    company_id = fields.Many2one(
        'res.company',
        related='approval_request_id.company_id',
        store=True,
        readonly=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Cuenta Analítica',
        required=True,
    )

    @staticmethod
    def _extract_first_int(value):
        if isinstance(value, int):
            return value
        if not isinstance(value, str):
            try:
                return int(value)
            except Exception:
                return False

        parts = [p.strip() for p in value.split(',') if p.strip()]
        for p in parts:
            if p.isdigit():
                return int(p)
        return False

    def _get_primary_analytic_from_distribution(self, distribution):
        if not distribution or not isinstance(distribution, dict):
            return False

        best_id = False
        best_pct = -1.0

        for key, pct in distribution.items():
            analytic_id = self._extract_first_int(key)
            if not analytic_id:
                continue
            try:
                pct_val = float(pct or 0.0)
            except Exception:
                pct_val = 0.0
            if pct_val > best_pct:
                best_pct = pct_val
                best_id = analytic_id

        return best_id

    def _get_project_analytic_account(self, request):
        if not request or 'project_id' not in request._fields:
            return False

        project = request.project_id
        if not project or 'account_id' not in project._fields:
            return False

        return project.account_id

    def _set_default_from_project_if_empty(self):
        for line in self:
            if line.analytic_distribution:
                continue
            req = line.approval_request_id
            aa = line._get_project_analytic_account(req)
            if aa:
                line.analytic_distribution = {aa.id: 100.0}
                line.analytic_account_id = aa.id

    @api.onchange('product_id', 'approval_request_id')
    def _onchange_default_analytic(self):
        self._set_default_from_project_if_empty()

    @api.onchange('analytic_distribution')
    def _onchange_analytic_distribution(self):
        for line in self:
            dist = line.analytic_distribution or {}
            if not dist:
                continue
            primary_id = line._get_primary_analytic_from_distribution(dist)
            if primary_id:
                line.analytic_account_id = primary_id

    @api.onchange('analytic_account_id')
    def _onchange_analytic_account_id(self):
        for line in self:
            if line.analytic_account_id and not line.analytic_distribution:
                line.analytic_distribution = {line.analytic_account_id.id: 100.0}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            dist = vals.get('analytic_distribution') or {}
            if dist and not vals.get('analytic_account_id'):
                primary_id = self._get_primary_analytic_from_distribution(dist)
                if primary_id:
                    vals['analytic_account_id'] = primary_id
            if vals.get('analytic_account_id') and not vals.get('analytic_distribution'):
                vals['analytic_distribution'] = {vals['analytic_account_id']: 100.0}
            if not vals.get('analytic_account_id') and vals.get('approval_request_id'):
                req = self.env['approval.request'].browse(vals['approval_request_id'])
                aa = self._get_project_analytic_account(req)
                if aa:
                    vals['analytic_account_id'] = aa.id
                    if not vals.get('analytic_distribution'):
                        vals['analytic_distribution'] = {aa.id: 100.0}

        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'analytic_distribution' in vals:
            for line in self:
                dist = line.analytic_distribution or {}
                if dist:
                    primary_id = line._get_primary_analytic_from_distribution(dist)
                    if primary_id:
                        line.analytic_account_id = primary_id
        if 'analytic_account_id' in vals:
            for line in self:
                if line.analytic_account_id and not line.analytic_distribution:
                    line.analytic_distribution = {line.analytic_account_id.id: 100.0}
        self._set_default_from_project_if_empty()

        return res