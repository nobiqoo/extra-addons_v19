# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

TYPE_PERIOD = [
    ('MONTHLY', 'Mensual'),
    ('BIWEEKLY', 'Quincenal')
]

TYPE_BIWEEKLY = [
    ('FIRST', 'Primera Quincena'),
    ('SECOND', 'Segunda Quincena')
]


class HrPeriod(models.Model):
    _name = 'hr.period'
    _description = 'Periodo de nómina'
    _order = 'name'

    name = fields.Char(string='Nombre', readonly=True)
    active = fields.Boolean(string='Activo')
    start = fields.Date(string='Inicio', readonly=True)
    end = fields.Date(string='Fin', readonly=True)
    type_period = fields.Selection(
        string='Tipo de periodo', selection=TYPE_PERIOD, readonly=True)
    type_biweekly = fields.Selection(
        string='Tipo de quincena', selection=TYPE_BIWEEKLY, readonly=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'allow_create' in vals and vals['allow_create']:
                vals.pop('allow_create')
            else:
                raise UserError(
                _('Ningun usuario tiene permitido crear periodos manualmente vaya al creador de periodos'))
        return super(HrPeriod, self).create(vals_list)

    def write(self, vals):
        new_vals = {'active': vals['active']} if 'active' in vals else {}
        return super(HrPeriod, self).write(new_vals)

    def get_period(self, date_from, date_to, type_period):
        if not date_from:
            return self.browse()
        if not date_to:
            return self.search([
                ('start', '<=', date_from), ('end', '>=', date_from),
                ('type_period', '=', type_period), ('active', '=', True),
                ('company_id', '=', self.env.company.id)
            ])
        return self.search([
            ('start', '<=', date_to), ('end', '>=', date_from),
            ('type_period', '=', type_period), ('active', '=', True),
            ('company_id', '=', self.env.company.id)
        ])

    def between(self, date):
        if not date:
            return False
        return self.start <= date <= self.end

    def get_days(self):
        days = []
        current_day = self.start
        while current_day <= self.end:
            days.append(current_day)
            current_day += timedelta(days=1)
        return days
