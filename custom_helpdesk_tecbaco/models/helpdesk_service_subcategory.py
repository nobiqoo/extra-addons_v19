# -*- coding: utf-8 -*-

from odoo import models, fields, api

class HelpdeskServiceSubcategory(models.Model):
    _name = 'helpdesk.service.subcategory'
    _description = "Helpdesk service subcategory"

    name = fields.Char(string="Nombre de la subcategoría")
    category_id = fields.Many2one('helpdesk.service.category', string="Categoría principal")
    partner_company_ids = fields.Many2many('res.partner', string="Compañías donde aplica")
    active = fields.Boolean(default=True)
    description = fields.Text(string="Descripción funcional")
    service_ids = fields.One2many('helpdesk.service.type', 'sub_category_id', string="Servicios pertenecientes a esta subcategoría")
    