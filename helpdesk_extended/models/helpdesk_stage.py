# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HelpdeskStage(models.Model):
    _inherit = 'helpdesk.stage'

    is_restricted = fields.Boolean('Etapa Inicial',
                                   help='Marque este campo, si desea que se restrinja la transición de etapa por '
                                   'el vendedor')
