# -*- coding: utf-8 -*-

from odoo import fields, models


class FetchmailServer(models.Model):
    _inherit = 'fetchmail.server'

    company_id = fields.Many2one(
        'res.company', 'Compañía',
        help='Compañía a la que pertenecen los correos que llegan por '
             'este servidor. Si se deja vacío, los correos recibidos '
             'por este servidor quedan en la compañía por defecto de '
             'quien procese el correo (comportamiento actual, sin '
             'cambios).')
