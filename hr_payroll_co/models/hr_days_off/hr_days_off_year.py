# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime


def get_years(self):
    year = datetime.now().year
    return [(str(y), str(y)) for y in range(year-5, year+2)]


class HrDaysOffYear(models.Model):
    _name = 'hr.days.off.year'
    _description = 'Days off year'

    name = fields.Char(string='Nombre', readonly=True)
    year = fields.Selection(string='Año', selection=get_years, required=True)
    days_off = fields.One2many(
        comodel_name='hr.day.off', inverse_name='year_id', string='Festivos')

    _year_uniq = models.Constraint(
        'UNIQUE (year)',
        'Ya existe un calendario de festivos con el año especificado.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = vals['year']
        return super(HrDaysOffYear, self).create(vals_list)

    def is_day_off(self, date):
        year = date.year
        years = self.search([('year', '=', str(year))])
        if not years:
            return False
        for day_off in years[0].days_off:
            if day_off.date == date:
                return True
        return False
