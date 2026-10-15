# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContractExtension(models.Model):
    _name = 'hr.contract.extension'
    _description = 'Prórroga de Contrato'
    _order = 'sequence'

    contract_id = fields.Many2one('hr.contract', 'Contrato')
    sequence = fields.Integer('Numero de Prórroga')
    date_from = fields.Date('Fecha de Inicio Prórroga')
    date_to = fields.Date('Fecha de Fin Prórroga')
