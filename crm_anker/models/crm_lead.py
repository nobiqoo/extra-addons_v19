# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    gestion_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Encargado de la gestión'
    )
    comertial_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Comercial asignado'
    )
    date_limit = fields.Date(
        string='Fecha limite Lead'
    )
    recommended = fields.Boolean(
        string='Recomendado'
    )
    database_id = fields.Many2one(
        comodel_name='crm.lead.database',
        string='Base de datos proveniente'
    )
    nvocc = fields.Boolean(
        string='NVOCC'
    )
    service_modality_ids = fields.Many2many(
        comodel_name='crm.tag',
        string='Modalidad de servicio'
    )
    partner_state = fields.Many2one(
        comodel_name='crm.lead.state',
        string='Estado del cliente'
    )
    partner_tags_ids = fields.Many2many(
        comodel_name='res.partner.category',
        string='Clasificación del cliente',
        compute='_compute_partner_tags_ids',
        store=True,
        readonly=False
    )
    industry_type_id = fields.Many2one(
        comodel_name='crm.lead.industry',
        string='Tipo de industria'
    )
    service_type_ids = fields.Many2many(
        comodel_name='crm.lead.service',
        string='Tipos de servicio'
    )
    partner_type_id = fields.Many2one(
        comodel_name='crm.lead.partner.type',
        string='Tipo de cliente'
    )
    trafic_line_ids = fields.One2many(
        comodel_name='crm.lead.trafic.line',
        inverse_name='crm_id',
        string='Líneas de trafico'
    )
    
    @api.depends('partner_id')
    def _compute_partner_tags_ids(self):
        for record in self:
            record.partner_tags_ids = record.partner_id.category_id
