# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.fields import Domain


class DianClaimConcept(models.Model):
    _name = 'dian.claim.concept'
    _inherit = ['mail.thread']
    _description = 'DIAN claim concepts'

    name = fields.Char('Name', tracking=True)
    dian_code = fields.Char('DIAN code', tracking=True)
    
    @api.depends('dian_code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s%s' % (record.dian_code and '[%s] ' % record.dian_code or '', record.name)

    @api.model
    def _name_search(self, name, domain=None, operator='ilike',
                     limit=None, order=None):
        domain = domain or []
        if operator != 'ilike' and not (name or '').strip():
            domain = Domain.AND([['|', ('name', operator, name),
                                      ('dian_code', operator, name)], domain])
        return self._search(domain, limit=limit, order=order)
