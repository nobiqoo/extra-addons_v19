# -*- coding: utf-8 -*-

from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    allow_in_website = fields.Boolean(
        string='Disponible en Sitio Web',
        copy=False
    )
    need_file_in_website = fields.Boolean(
        string='¿Es requerido archivo en Sitio Web?',
        copy=False
    )
    is_from_website = fields.Boolean(
        string='Creada desde Sitio Web'
    )