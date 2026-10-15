# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HRFiscalType(models.Model):
    _name = 'hr.fiscal.type'
    _description = 'Tipo de Cotizante'

    name = fields.Char(string='Nombre', size=64, required=True)
    code = fields.Char(string='Código', size=64, required=True)
    note = fields.Text(string='Notas')

    _name_uniq = models.Constraint(
        'UNIQUE (name)',
        'El Nombre tiene que ser unico!',
    )
    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'El Codigo tiene que ser unico!',
    )
