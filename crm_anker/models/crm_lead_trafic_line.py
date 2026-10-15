# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo.exceptions import ValidationError


class CrmLeadTraficLine(models.Model):
    _name = 'crm.lead.trafic.line'
    _description = 'Líneas de trafico CRM'

    crm_id = fields.Many2one(
        comodel_name='crm.lead',
        string='Oportunidad',
        required=True
    )
    origin_country_id = fields.Many2one(
        comodel_name='crm.lead.country',
        string='País origen',
        required=True
    )
    origin_city_id = fields.Many2one(
        comodel_name='crm.lead.city',
        string='Ciudad origen',
        required=True
    )
    dest_country_id = fields.Many2one(
        comodel_name='crm.lead.country',
        string='País destino',
        required=True
    )
    dest_city_id = fields.Many2one(
        comodel_name='crm.lead.city',
        string='Ciudad destino',
        required=True
    )
    transport_id = fields.Many2one(
        comodel_name='crm.lead.transport',
        string='Tipo de transporte',
        required=True
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Líneas de trafico',
        compute='_compute_partner_id',
        store=True
    )

    @api.depends('crm_id', 'crm_id.partner_id')
    def _compute_partner_id(self):
        for record in self:
            record.partner_id = record.crm_id.partner_id
