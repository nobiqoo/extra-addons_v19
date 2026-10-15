# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class TransportLocation(models.Model):
    
    _name = 'transport.location'
    _inherit = 'wk.company.visibility.mixin'
    _description = 'Transport Location'
    
    name = fields.Char(string='Location Name', required=True, help="Name of the transport location")
    street = fields.Char(string='Street', required=True, help="Street address of the transport location")
    city = fields.Char(string='City', required=True, help="City of the transport location")
    zip = fields.Char(string='ZIP', required=True, help="ZIP code of the transport location")
    state_id = fields.Many2one('res.country.state', string='State', required=True, help="State of the transport location", ondelete='restrict', domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one('res.country', string='Country', required=True, help="Country of the transport location", ondelete='restrict')
    company_id = fields.Many2one('res.company', string='School', default=lambda self: self.env.company, help="School associated with this transport location", required=True)
    
    @api.onchange('country_id')
    def _onchange_country_id(self):
        if self.country_id and self.country_id != self.state_id.country_id:
            self.state_id = False

    @api.onchange('state_id')
    def _onchange_state(self):
        if self.state_id.country_id and self.country_id != self.state_id.country_id:
            self.country_id = self.state_id.country_id