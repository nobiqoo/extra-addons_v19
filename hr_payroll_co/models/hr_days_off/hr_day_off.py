# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrDayOff(models.Model):
    _name = 'hr.day.off'
    _description = 'Day off'

    name = fields.Char(string='Nombre', required=True)
    date = fields.Date(string='Fecha', required=True)
    year_id = fields.Many2one(
        comodel_name='hr.days.off.year', string='Año', required=True, ondelete='cascade')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            year_model = self.env['hr.days.off.year']
            year_id = year_model.browse(vals['year_id'])
            current_year = vals['date'][:4]
            self._validate_date(year_id, current_year, vals['name'])
        return super(HrDayOff, self).create(vals_list)

    def write(self, values):
        current_year = values.get('date', str(self.date.year))[:4]
        self._validate_date(self.year_id, current_year, self.name)
        return super(HrDayOff, self).write(values)

    def _validate_date(self, year_id, current_year, name):
        context_year = year_id.year
        if context_year != current_year:
            raise ValidationError(
                f'El registro {name} no pertenece al año {context_year}')
        return True
