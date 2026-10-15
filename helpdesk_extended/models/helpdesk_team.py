# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    web_technician_req = fields.Boolean('Technician required in web form',
                                        default=False)

    @api.model
    def _get_field_modules(self):
        res = super(HelpdeskTeam, self)._get_field_modules()
        if self.env['ir.module.module'].search(
                [('name', '=', 'website_helpdesk_form_extended')]):
            res['use_website_helpdesk_form'] = \
                'website_helpdesk_form_extended'
        else:
            raise ValidationError(_(
                'There is no module with the name '
                '"website_helpdesk_form_extended" in this database.'
            ))
        return res
