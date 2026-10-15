# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.fields import Domain


class DianConceptType(models.Model):
    _name = 'dian.concept.type'
    _description = 'Tipo concepto DIAN'

    name = fields.Char('Nombre')
    dian_code = fields.Char('Código DIAN')
    percentage = fields.Float('Porcentaje')
    type = fields.Selection([('dev', 'Devengos'),
                             ('ded', 'Deducciones'),
                             ('overtime', 'Horas extra')],
                            'Tipo')
    active = fields.Boolean('Activo',
                    default=True)
    
    @api.depends('type', 'dian_code', 'name')
    def _compute_display_name(self):
        res = []
        for record in self:
            typec = {
                'dev': 'DEV',
                'ded': 'DED',
                'overtime': 'EXT'
            }
            name = u'[%s-%s] %s' % (
                typec.get(record.type, ''),
                record.dian_code or '',
                record.name)
            record.display_name = name

    @api.model
    def _name_search(self, name, domain=None, operator='ilike',
                     limit=None, order=None):
        domain = domain or []
        if operator != 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = Domain.AND([['|', ('name', operator, name),
                                      ('dian_code', '=ilike', name)], domain])
        return self._search(domain, limit=limit, order=order)
