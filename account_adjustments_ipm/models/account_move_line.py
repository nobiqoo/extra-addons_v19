# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    description = fields.Text(string='Descripción', help='Descripción o detalle de la línea de movimiento contable.')
