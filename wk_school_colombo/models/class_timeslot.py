# -*- coding: utf-8 -*-
from odoo import fields, models


class WkClassTimeslot(models.Model):
    """Agrega Sede a Franjas horarias, para poder filtrar/clasificar cada
    franja por la Sede configurable a la que pertenece.
    """

    _inherit = 'wk.class.timeslot'

    sede_id = fields.Many2one('wk.school.colombo.sede', string="Sede")
