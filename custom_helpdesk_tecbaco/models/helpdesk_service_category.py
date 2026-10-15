# -*- coding: utf-8 -*-

from odoo import models, fields, api

class HelpdeskServiceCategory(models.Model):
    _name = 'helpdesk.service.category'
    _description= "Helpdesk service category"

    name = fields.Char(string="Nombre de la categoría")
    partner_company_ids = fields.Many2many('res.partner',string="Compañías donde ésta categoría está disponible.")
    active = fields.Boolean(default=True)
    description = fields.Text(string="Descripción funcional de la categoría")
    sub_category_ids = fields.One2many('helpdesk.service.subcategory', 'category_id', string='Subcategorías asociadas')


  