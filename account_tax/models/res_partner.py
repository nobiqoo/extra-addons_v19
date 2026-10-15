# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    classification_id = fields.Many2one(
        comodel_name='res.partner.classification',
        string='ISIC Main'
    )

    classifications_ids = fields.Many2many(
        comodel_name='res.partner.classification',
        string='ISIC Minor'
    )
    economic_subactivity = fields.Char(string='Subactividad económica')


class ResPartnerClassification(models.Model):
    _name = 'res.partner.classification'
    _description = 'ISIC'
    _order = 'code'
    _rec_name = 'code'

    _sql_constraints = [(
        'unique_code',
        'unique(company_id, code)',
        'The code must be unique per company!'
    )]

    classification_ids = fields.One2many(
        comodel_name='res.city.classification',
        inverse_name='classification_id',
        string='Retention rates'
    )

    code = fields.Char(
        string='Code',
        required=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
    )

    name = fields.Char(
        string='Name',
        required=True
    )
