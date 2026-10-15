# -*- coding: utf-8 -*-
from odoo import models, fields


class HrContractDisciplinaryLine(models.Model):
    _name = 'hr.contract.disciplinary.line'
    _description = "Procesos Disciplinarios"

    contract_id = fields.Many2one('hr.contract', string='Contrato')
    date = fields.Date(string='Fecha', required=True)
    type_id = fields.Many2one('disciplinary.type', string='Tipo', required=True)
    file = fields.Binary(string="Archivo", attachment=True)
    filename = fields.Char(string='Nombre del archivo')
    observation = fields.Text(string='Observación', required=True)


class DisciplinaryType(models.Model):
    _name = 'disciplinary.type'
    _description = 'Tipo de Proceso Disciplinario'

    name = fields.Char(string='Nombre')
