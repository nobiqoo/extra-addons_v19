# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    overtime_tolerance_minutes = fields.Integer(
        string='Tolerancia Horas Extras (min)',
        default=0,
        help='Minutos mínimos de tiempo trabajado después del turno para que se '
             'genere una novedad de horas extras.\n'
             'Ejemplo: 30 → solo se genera H.E. si el empleado sale ≥ 30 min '
             'después de la hora de fin del turno.\n'
             '0 = sin tolerancia (cualquier minuto genera H.E.).',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    overtime_tolerance_minutes = fields.Integer(
        related='company_id.overtime_tolerance_minutes',
        string='Tolerancia Horas Extras (min)',
        readonly=False,
    )
