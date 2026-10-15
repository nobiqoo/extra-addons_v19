# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.fields import Domain


class DianUomCode(models.Model):
    _name = 'dian.uom.code'
    _inherit = ['mail.thread']
    _description = 'Unidad de medida definida por la DIAN'

    name = fields.Char('Nombre', tracking=True)
    dian_code = fields.Char('Código DIAN', tracking=True)

    @api.depends('dian_code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s%s' % (record.dian_code and '[%s] ' % record.dian_code or '', record.name)

    @api.model
    def _name_search(self, name, domain=None, operator='ilike',
                     limit=None, order=None):
        domain = domain or []
        if operator != 'ilike' and not (name or '').strip():
            domain = Domain.AND([['|', ('name', 'ilike', name),
                                      ('dian_code', 'ilike', name)], domain])
        return self._search(domain, limit=limit, order=order)
