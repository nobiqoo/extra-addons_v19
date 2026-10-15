# -*- coding: utf-8 -*-
from odoo import models, fields


class WkGradeSubjects(models.Model):
    _inherit = 'wk.grade.subjects'

    is_active_subject = fields.Boolean(string="Activa", default=True)
