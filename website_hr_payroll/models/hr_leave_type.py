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
    enable_approval_flow = fields.Boolean(
        string='Habilitar flujo de aprobación',
        default=False,
        help='Habilita los botones y correos del flujo de aprobación (mentor y usuarios de nómina).',
    )
    enable_button_notify = fields.Boolean(
        string='Habilitar botón para notificación manual',
        default=False,
        help='Muestra el botón "Notificar aprobación" cuando la ausencia está validada.',
    )
