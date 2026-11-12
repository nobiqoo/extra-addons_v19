# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    leave_notifier_website = fields.Boolean(
        string='¿Notificar por correo ausencias a instructor?',
        default=False,
        help='Si está activo, se enviará una notificación por correo electrónico al instructor '
             'cuando un empleado cree una ausencia a través del sitio web.',
    )
    leave_notifier_website_employee = fields.Boolean(
        string='¿Notificar por correo ausencias a empleados?',
        default=False,
        help='Si está activo, se enviará una notificación por correo electrónico al empleado '
             'cuando cree una ausencia a través del sitio web.',
    )
    leave_notifier_payroll_users_website = fields.Boolean(
        string='¿Notificar por correo ausencias a usuarios de nómina?',
        default=False,
        help='Si está activo, se enviará una notificación por correo electrónico a los usuarios '
             'de nómina cuando un empleado cree una ausencia a través del sitio web.',
    )
    payroll_users_ids = fields.Many2many(
        comodel_name='res.users',
        relation='res_company_payroll_users_rel',
        column1='company_id',
        column2='user_id',
        string='Usuarios notificadores de nómina',
        help='Usuarios que recibirán las notificaciones de ausencias creadas desde el sitio web.',
    )
