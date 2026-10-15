
# -*- coding: utf-8 -*-

from odoo import api, models, fields
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_maintenance_product = fields.Boolean(
        string='Es Equipo de Mantenimiento',
        tracking=True
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente'
    )
    is_spare_part = fields.Boolean(string="¿Es Repuesto?")
    tempario_ids = fields.Many2many(
        'maintenance.tempario',
        string='Temparios'
    )

