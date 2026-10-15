# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.fields import Domain


class DianTypeCode(models.Model):
    _name = 'dian.type_code'
    _inherit = ['mail.thread']
    _description = 'Representaciones, Obligaciones, Aduanas y ' \
                    'Establecimientos definidos por la DIAN'

    dian_code = fields.Char('Código DIAN',
                    required=True,
                    tracking=True)
    name = fields.Char('Descripción',
                    required=True,
                    tracking=True)
    type = fields.Selection(
                    [('representation', 'Representation'),
                     ('obligation', 'Obligation'),
                     ('customs', 'Customs'),
                     ('establishment', 'Establishment')],
                    'Tipo',
                    required=True,
                    tracking=True)
    is_required_dian = fields.Boolean('Vigente para FE',
                    tracking=True)

    @api.depends('dian_code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = '%s%s' % (record.dian_code and '[%s] ' % record.dian_code or '', record.name)

    @api.model
    def _name_search(self, name, domain=None, operator='ilike',
                     limit=None, order=None):
        domain = domain or []
        if operator != 'ilike' and not (name or '').strip():
            domain = Domain.AND([['|', ('dian_code', 'ilike', name),
                                      ('name', 'ilike', name)], domain])
        return self._search(domain, limit=limit, order=order)
