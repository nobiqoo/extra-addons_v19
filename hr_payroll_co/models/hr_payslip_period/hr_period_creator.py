# -*- coding: utf-8 -*-
import calendar
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from .hr_period import TYPE_PERIOD
from .hr_period import TYPE_BIWEEKLY


def get_years():
    year = datetime.now().year
    return [(str(y), str(y)) for y in range(year-5, year+6)]


MONTHS = [
    ('00', 'Todos'),
    ('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'),
    ('04', 'Abril'), ('05', 'Mayo'), ('06', 'Junio'),
    ('07', 'Julio'), ('08', 'Agosto'), ('09', 'Septiembre'),
    ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
]


def get_end_day_month(year, month):
    if isinstance(year, str):
        year = int(year)
    if isinstance(month, str):
        month = int(month)
    return calendar.monthrange(year, month)[1]


class HrPeriodCreator(models.TransientModel):
    _name = 'hr.period.creator'
    _description = 'Creador de periodos de nómina'
    _order = 'year'

    year = fields.Selection(
        string='Año', selection=lambda self: get_years(), required=True)
    month = fields.Selection(string="Mes", selection=MONTHS, required=True)
    type_period = fields.Selection(
        string="Tipo de periodo", selection=TYPE_PERIOD + [('ALL', 'Todos')], required=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Compañia', required=True)
    notes = fields.Text(string='Notas', readonly=True)

    def create_periods(self):
        hr_period = self.env['hr.period']
        self.notes = ''
        new_periods = []
        list_periods = [self.year + '-' + month[0] for month in MONTHS[1:]
                        ] if self.month == '00' else [self.year + '-' + self.month]
        for period in list_periods:
            periods = []
            if self.type_period == 'MONTHLY':
                periods.append(self.create_period_monthly_biweekly(
                    period, 'MONTHLY', False))
            elif self.type_period == 'BIWEEKLY':
                periods.append(self.create_period_monthly_biweekly(
                    period, 'BIWEEKLY', 'FIRST'))
                periods.append(self.create_period_monthly_biweekly(
                    period, 'BIWEEKLY', 'SECOND'))
            else:
                periods.append(self.create_period_monthly_biweekly(
                    period, 'MONTHLY', False))
                periods.append(self.create_period_monthly_biweekly(
                    period, 'BIWEEKLY', 'FIRST'))
                periods.append(self.create_period_monthly_biweekly(
                    period, 'BIWEEKLY', 'SECOND'))

            periods, notes = self.search_duplicate(periods, hr_period)
            new_periods += periods
            self.notes += notes
        hr_period.create(new_periods)
        return {
            'name': 'Creador de periodos de nómina',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'hr.period.creator',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': self.id,
        }

    def create_period_monthly_biweekly(self, date, type_period, type_biweekly):
        name = date.replace('-', '/')
        if type_period == 'MONTHLY':
            start = date + '-01'
            end = date + '-%s' % (get_end_day_month(*date.split('-')))
        else:
            name += ' Q%s' % ('1' if type_biweekly == 'FIRST' else '2')
            start = date + ('-01' if type_biweekly == 'FIRST' else '-16')
            end = date + ('-%s' % (get_end_day_month(*date.split('-')))
                          if type_biweekly == 'SECOND' else '-15')
        period = {
            'name': name,
            'active': True,
            'start': start,
            'end': end,
            'type_period': type_period,
            'type_biweekly': type_biweekly,
            'company_id': self.company_id.id,
            'allow_create': True,
        }
        return period

    def search_duplicate(self, periods, hr_period):
        notes = ''
        flag_win = True
        periods2remove = []
        for period in periods:
            if hr_period.search([('name', '=', period['name']), ('company_id', '=', period['company_id'])]):
                periods2remove.append(period)
                notes += 'Ya existe el periodo %s\n' % period['name']
                flag_win = False
            else:
                notes += 'El periodo se ha creado %s\n' % period['name']
        for p2p in periods2remove:
            periods.remove(p2p)
        return periods, notes
