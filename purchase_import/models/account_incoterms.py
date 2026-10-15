# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountIncoterms(models.Model):
    _inherit = 'account.incoterms'

    incoterms_type = fields.Selection(
        selection=[
            ('ge', 'Group E'),
            ('gf', 'Group F'),
            ('gc', 'Group C'),
            ('gd', 'Group D'),
        ],
        string='Group'
    )

    def name_get(self):
        result = []
        for record in self:
            name = '[%s] %s' % (record.code, record.name)
            result.append((record.id, name))
        return result
