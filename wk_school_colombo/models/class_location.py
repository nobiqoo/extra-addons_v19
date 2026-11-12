# -*- coding: utf-8 -*-
from odoo import fields, models


class WkClassLocation(models.Model):
    """Agrega Sede a Ubicaciones (Salones), para poder filtrar/clasificar
    cada Ubicación por la Sede configurable a la que pertenece.
    """

    _inherit = 'wk.class.location'

    sede_id = fields.Many2one('wk.school.colombo.sede', string="Sede")
