# -*- coding: utf-8 -*-

from uuid import uuid4


from odoo import models, fields, api, http, _
from odoo.exceptions import ValidationError


class ExcelDataSearch(models.Model):
    _name = 'excel.data.search'
    _description = 'Table generator for excel'

    active = fields.Boolean('Active',
                            default=True)
    name = fields.Char('Name')
    description = fields.Char('Description')
    query_type = fields.Selection([('direct', 'Direct')],
                                  'Query type',
                                  default='direct')
    query = fields.Text('SQL Query')
    type_out = fields.Selection(
        [('json', 'JSON'),
         ('table', 'Table')],
        'Output type',
        default='json')
    # token
    access_key = fields.Char('Access key')
    url = fields.Char('Url',
                      compute='_compute_url',
                      store=True)

    @api.depends('access_key')
    def _compute_url(self):
        for record in self:
            if record.access_key:
                base_url = http.request.httprequest.host_url
                url = '{base}odc15/{key}'.format(base=base_url,
                                                 key=record.access_key)
                record.url = url
                print('crear url')
            else:
                record.url = False

    @api.model_create_multi
    def create(self, vals_list):
        res = super(ExcelDataSearch, self).create(vals_list)
        for record in res:
            record.access_key_assign()
        return res

    def access_key_assign(self):
        self.ensure_one()
        c = 0
        same_key = 0
        while c <= 10 or same_key > 0:
            self.access_key = uuid4()
            excel_obj = self.env['excel.data.search']
            same_key = excel_obj.search_count(
                [('access_key', '=', self.access_key),
                 ('id', '!=', self.id)])
            c += 1
        if c > 10 and same_key > 0:
            raise ValidationError(
                _('The access key is already used by another document'))
