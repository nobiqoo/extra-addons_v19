# -*- coding: utf-8 -*-

from odoo import fields, models


class L10nLatamIdentificationType(models.Model):
    _inherit = 'l10n_latam.identification.type'

    code_cw = fields.Char('CW code')
