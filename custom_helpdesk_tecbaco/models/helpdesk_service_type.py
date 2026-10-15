# -*- coding: utf-8 -*-

from odoo import models, fields, api

TICKET_PRIORITY = [
    ('0', 'Low priority'),
    ('1', 'Medium priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),
]

class HelpdeskServiceType(models.Model):
    _name = 'helpdesk.service.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tipo de servicio mesa de ayuda'

    name = fields.Char(string="Nombre del servicio específico")
    category_id = fields.Many2one('helpdesk.service.category', string="Categoría")
    sub_category_id = fields.Many2one('helpdesk.service.subcategory', string="Subcategoría asociada")
    partner_company_ids = fields.Many2many('res.partner', string="Compañías donde el servicio aplica")
    description = fields.Text(string="Descripción del servicio")
    active = fields.Boolean(default=True)
    team_ids = fields.Many2many('helpdesk.team', string="Equipos de helpdesk que prestan este servicio")
    priority = fields.Selection(TICKET_PRIORITY, string='Prioridad', default='0', tracking=True)
  
  # Compute field for dinamic domain for category_id
    allowed_category_ids = fields.Many2many(
        'helpdesk.service.category',
        compute='_compute_allowed_categories',
        store=False
    )
    
    @api.depends('sub_category_id')
    def _compute_allowed_categories(self):
        for record in self:
            if record.sub_category_id and record.sub_category_id.category_id:
                record.allowed_category_ids = record.sub_category_id.category_id
            else:
                # get all the categories
                record.allowed_category_ids = self.env['helpdesk.service.category'].search([])
    
    @api.onchange('sub_category_id')
    def _onchange_sub_category_id(self):
        if self.sub_category_id and self.sub_category_id.category_id:
            self.category_id = self.sub_category_id.category_id
            return {
                'domain': {
                    'category_id': [('id', 'in', self.allowed_category_ids.ids)]
                }
            }
        return {'domain': {'category_id': []}}
    
    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            if self.sub_category_id and self.sub_category_id.category_id != self.category_id:
                self.sub_category_id = False
            return {
                'domain': {
                    'sub_category_id': [('category_id', '=', self.category_id.id)]
                }
            }
        else:
            self.sub_category_id = False
            return {'domain': {'sub_category_id': []}}
