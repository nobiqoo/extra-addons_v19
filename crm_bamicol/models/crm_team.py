# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    require_architect = fields.Boolean(
        string='Requiere Arquitecto',
        default=False,
        help=(
            'Cuando está activo, el campo "Arquitecto" será obligatorio '
            'en los leads, oportunidades y cotizaciones asignados a este '
            'equipo de ventas (ej. canal Arquitectos o Proyectos).'
        ),
    )
