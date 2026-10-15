# -*- coding: utf-8 -*-
from odoo import fields, models


class GradeScaleLine(models.Model):
    _inherit = 'wk.grade.scale.line'

    passes = fields.Boolean(
        string="¿Aprueba?", default=True,
        help="Indica si este tramo de la escala se considera una nota "
             "aprobatoria. Por defecto todos los tramos aprueban: revise y "
             "desmarque los que correspondan a una nota reprobatoria (por "
             "ejemplo, el tramo mínimo).")
