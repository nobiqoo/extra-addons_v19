# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HRContractRisk(models.Model):
    _name = 'hr.contract.risk'
    _description = 'Riesgo Laboral'

    name = fields.Char(string='Riesgo')
    risk_percentage = fields.Float(
        string='Porcentaje de Riesgo', digits=(16, 6))
