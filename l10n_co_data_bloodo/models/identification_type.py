# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.fields import Domain


class IdentificationType(models.Model):
    _inherit = 'l10n_latam.identification.type'

    dian_code = fields.Char('Código DIAN')

    @api.depends('dian_code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s%s' % (record.dian_code and '[%s] ' % record.dian_code or '', record.name)

    @api.model
    def _name_search(self, name, domain=None, operator='ilike',
                     limit=None, order=None):
        domain = domain or []
        if operator != 'ilike' and not (name or '').strip():
            domain = expression.AND([['|', ('name', 'ilike', name),
                                      ('dian_code', 'ilike', name)], domain])
        return self._search(domain, limit=limit, order=order)
