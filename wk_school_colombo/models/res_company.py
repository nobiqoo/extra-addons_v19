# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    accounting_reclassification_user_id = fields.Many2one(
        'res.users', string="Responsable de reclasificación contable",
        help="Usuario que recibe la actividad de reclasificación contable "
             "cuando se aplaza a un estudiante. Si se deja vacío, la "
             "actividad queda asignada a quien confirme el aplazamiento.")
