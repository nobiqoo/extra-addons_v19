# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # consol
    networks_ids = fields.Many2many(
        comodel_name='res.partner.network',
        string='Networks'
    )


class ResPartnerNetWork(models.Model):
    _name = 'res.partner.network'
    _description = 'Partner Network'

    name = fields.Char(string='Name')
