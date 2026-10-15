# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class CodeCIE10Table(models.Model):
    _name = 'hr.leave.code.cie10.table'
    _description = 'CIE10 Table'
    _rec_name = 'code'

    code = fields.Char('Código CIE10', required=True)
    name = fields.Text('Descripción del Diagnósitco', required=True)

    _code_uniq = models.Constraint(
        'UNIQUE (code)',
        'El código CIE10 ya existe.',
    )