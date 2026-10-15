# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PygPositionWizard(models.TransientModel):
    _name = 'pyg.position.wizard'
    _description = 'P&G por posición wizard'

    name = fields.Char('Nombre')
    account_root_ids = fields.Many2many('account.account', 'pyg_wizard_account_root_rel', 'wizard_id', 'account_id', string='Raíz de cuenta')
    account_ids = fields.Many2many('account.account', string='Cuentas')
    analytic_account_ids = fields.Many2many('account.analytic.account', string='Cuentas analíticas')
    template_id = fields.Many2one('pyg.position.report.filter', 'Plantilla filtro')

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.name = self.template_id.name or False
            self.account_root_ids = self.template_id.account_root_ids.ids or False
            self.account_ids = self.template_id.account_ids.ids or False
            self.analytic_account_ids = self.template_id.analytic_account_ids.ids or False
        else:
            self.name = False
            self.account_root_ids = False
            self.account_ids = False
            self.analytic_account_ids = False

    def _build_domain(self):
        domain = []
        if self.account_root_ids:
            prefixes = [acc.code[:2] for acc in self.account_root_ids if acc.code]
            domain.append(('account_root_id', 'in', prefixes))
        if self.account_ids:
            domain.append(('account_id', 'in', self.account_ids.ids))
        if self.analytic_account_ids:
            domain.append(('analytic_account_id', 'in', self.analytic_account_ids.ids))
        return domain

    def view_report(self):
        self.ensure_one()
        action = self.env.ref('account_pyg.pyg_position_report_action').read()[0]
        action['domain'] = self._build_domain()
        return action

    def generate_xlsx(self):
        self.ensure_one()
        records = self.env['pyg.position.report'].search(self._build_domain())
        accounts_data = {}
        for rec in records:
            key = rec.analytic_account_id.id if rec.analytic_account_id else 0
            name = (rec.analytic_account_id.name if rec.analytic_account_id else 'Sin cuenta analítica')[:31]
            if key not in accounts_data:
                accounts_data[key] = {'name': name, 'line_ids': []}
            accounts_data[key]['line_ids'].append({
                'type_doc': rec.type_doc or '',
                'move': rec.document_id.name if rec.document_id else rec.document_ref or '',
                'date': str(rec.document_date) if rec.document_date else '',
                'partner': rec.partner_name or '',
                'profit': rec.profit or 0.0,
                'loss': rec.loss or 0.0,
                'profitability': rec.profitability_company or 0.0,
                'profitability_usd': rec.profit_usd or 0.0,
                'profitability_doc': rec.profitability_doc or 0.0,
                'currency': rec.currency or '',
                'rate': rec.rate or 0.0,
                'name': rec.detail or '',
                'origin': rec.doc_origin or '',
                'destination': rec.doc_destination or '',
                'motor': rec.doc_motor or '',
                'weight': rec.doc_weight or '',
                'position': rec.doc_position or '',
                'hbl': rec.doc_hbl or '',
                'volume': rec.doc_volume or '',
                'eta': str(rec.doc_eta) if rec.doc_eta else '',
                'salesman': rec.doc_salesman or '',
            })
        data = {'account_ids': list(accounts_data.values())}
        return self.env.ref('account_pyg.pyg_position_report_xlsx').report_action(self, data=data, config=False)
