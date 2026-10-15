# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HRContractWithholdingLog(models.Model):
    _name = 'hr.contract.withholding.log'
    _description = 'Retenciones Calculadas Procedimiento 2'

    name = fields.Char(string='Descripción')
    value = fields.Char(string='Detalle')
    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract')
