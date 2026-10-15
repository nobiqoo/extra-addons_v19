# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime

YEARS = [(str(x), str(x))
         for x in range(datetime.now().year - 5, datetime.now().year + 6)]

MONTHS = [
    ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
    ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
    ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
]


class EconomicVariablesLine(models.Model):
    _name = 'economic.variable.line'
    _description = 'Línea de variable económica'
    _order = 'id'

    variable_id = fields.Many2one(
        comodel_name='economic.variable', string='Variable económica')
    year = fields.Selection(string='Año', selection=YEARS)
    month = fields.Selection(
        string='Mes', selection=MONTHS, default='1', required=True)
    value = fields.Float(string='Valor')
    variable_line_detail_ids = fields.One2many(
        comodel_name='economic.variable.line.detail', inverse_name='variable_line_id',
        string='Detalles de línea de variable económica')
    variable_code = fields.Char(related='variable_id.code', store=True)
    month_int = fields.Integer(string='Mes Int', compute='_compute_month_int', store=True)

    _line_uniq = models.Constraint(
        'UNIQUE (variable_id, year, month)',
        'Ya está definido un valor para esta variable económica en el año y mes especificado.',
    )

    @api.depends('month')
    def _compute_month_int(self):
        for record in self.filtered(lambda x: x.month):
            record.month_int = int(record.month)
