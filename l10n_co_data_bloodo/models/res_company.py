# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    duplicate_contacts = fields.Boolean(
        string='Activate Duplicate Contacts', default=True)
    fiscal_position_local = fields.Boolean(
        'Posición Fiscal Local',
        compute='_compute_fiscal_position_local',
        help='Indica si la empresa está usando el plan de cuentas local')

    city_id = fields.Many2one('res.city',
                              'Ciudad',
                              compute='_compute_address',
                              inverse='_inverse_city',
                              domain="[('state_id', '=?', state_id)]")

    @api.depends('chart_template')
    def _compute_fiscal_position_local(self):
        """ Compute fiscal position local based on chart template. """
        for company in self:
            if company.chart_template == 'co':
                company.fiscal_position_local = True
            else:
                company.fiscal_position_local = False

    def _inverse_city(self):
        for company in self:
            company.partner_id.city_id = company.city_id

    def _get_company_address_field_names(self):
        res = super(ResCompany, self)._get_company_address_field_names()
        res.append('city_id')
        return res

    @api.onchange('city_id')
    def _onchange_city(self):
        if self.city_id.state_id:
            self.state_id = self.city_id.state_id