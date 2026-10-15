# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HelpdeskSupportType(models.Model):
    _name = 'helpdesk.support.type'
    _description = 'Helpdesk support type'

    name = fields.Char(string="Nombre del tipo de soporte")
    code = fields.Char(string="Código corto")
    active = fields.Boolean(default=True)
    description = fields.Text(string="Detalle funcional del tipo")



