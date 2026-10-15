# -*- coding: utf-8 -*-

from odoo import fields, models


class IrSequenceDateRange(models.Model):
    _inherit = 'ir.sequence.date_range'

    edi_resolution = fields.Char('Resolución')
    number_from = fields.Integer('Número inicial',
                                default=False)
    number_to = fields.Integer('Número final',
                                default=False)
    active_resolution = fields.Boolean('Resolución activa')
    prefix = fields.Char('Prefijo')
