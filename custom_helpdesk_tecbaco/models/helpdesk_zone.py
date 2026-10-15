# -*- coding: utf-8 -*-

from odoo import models, fields, api

class HelpdeskZone(models.Model):
    _name = "helpdesk.zone"
    _description="Helpdesk zone"

    name = fields.Char(string="Nombre de la zona")
    partner_company_ids = fields.Many2many('res.partner',string="Compañías donde aplica.")
    description = fields.Text(string="Detalle")
    active = fields.Boolean(default=True)
    rule_ids = fields.One2many(
        'helpdesk.zone.rule',
        'zone_id',
        string='Correos y prioridad'
    )
    
