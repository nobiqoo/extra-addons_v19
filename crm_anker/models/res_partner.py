# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    trafic_line_ids = fields.One2many(
        comodel_name='crm.lead.trafic.line',
        inverse_name='partner_id',
        string='Líneas de trafico'
    )
