# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContractAnalyticDistribution(models.Model):
    _name = 'hr.contract.analytic.distribution'
    _description = 'Distribucion analitica del contrato'

    analytic_account_id = fields.Many2one(
        string='Cuenta Analítica',
        comodel_name='account.analytic.account', required=True)
    rate = fields.Float(string='Distribución (%)', digits=(3, 3))
    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract')
