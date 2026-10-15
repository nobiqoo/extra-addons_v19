# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # @api.model
    # def create_from_ui(self, partner):
    #     partner_obj = self.env['res.partner']
    #     pid = partner.get('id', False)
    #     if pid and partner.get('name', False):
    #         partner_id = partner_obj.browse(pid)
    #         if partner.get('company_type', '') == 'person' \
    #             or (not partner.get('company_type', False) \
    #                 and partner_id.company_type == 'person'):
    #             partner.pop('name', False)
    #     res = super(ResPartner, self).create_from_ui(partner)
    #     partner_id = partner_obj.browse(res)
    #     partner_id._onchange_full_name()

    #     return res
