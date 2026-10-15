# -*- coding: utf-8 -*-

from odoo import models, fields


class PygPositionReportFilter(models.Model):
    _name = 'pyg.position.report.filter'
    _description = 'Plantilla de filtros PyG por posición'

    name = fields.Char('Nombre')
    account_ids = fields.Many2many('account.account', string='Cuentas')
    analytic_account_ids = fields.Many2many('account.analytic.account', string='Cuentas analíticas')
    account_root_ids = fields.Many2many('account.account', 'pyg_filter_account_root_rel', 'filter_id', 'account_id', string='Raíz de cuenta')
    company_id = fields.Many2one(
        'res.company',
        'Compañía',
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        (
            'name_by_company_unique',
            'unique(name, company_id)',
            'El nombre de la plantilla debe ser único por compañía.',
        )
    ]
