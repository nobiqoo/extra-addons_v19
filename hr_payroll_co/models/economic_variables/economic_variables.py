# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class EconomicVariables(models.Model):
    _name = 'economic.variable'
    _description = 'Variable económica'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, readonly=False)
    code = fields.Char(string='Código', required=True, readonly=False)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)
    variable_line_ids = fields.One2many(
        comodel_name='economic.variable.line', inverse_name='variable_id',
        string='Líneas de variable económica')
    location_code = fields.Char(
        string='Código de localización', compute='_compute_location_code', store=True)

    @api.depends('company_id.chart_template')
    def _compute_location_code(self):
        for record in self:
            record.location_code = record.company_id.chart_template

    _variable_uniq = models.Constraint(
        'UNIQUE (company_id, code)',
        'Ya está definida la variable económica.',
    )

    @api.model
    def get_value_by_date(self, code, date_ref):
        company_id = self.env.company.id
        variables = self.search([
            ('active', '=', True),
            ('code', '=', code),
            ('company_id', '=', company_id)
        ])

        if not variables:
            raise ValidationError(
                f"No se encontró una variable económica activa con el código '{code}' "
                f"para la compañía '{self.env.company.name}'. Por favor, configúrela."
            )

        if len(variables) > 1:
            raise ValidationError(
                f"Se encontraron {len(variables)} variables económicas activas con el código '{code}'. "
                f"Debe haber solo una. Por favor, revise y desactive los duplicados."
            )

        variable = variables

        year = date_ref.year
        month = date_ref.month

        domain = [
            ('variable_id', '=', variable.id),
            ('year', '=', str(year)),
            ('month_int', '<=', month)
        ]
        line = self.env['economic.variable.line'].search(
            domain, order='month desc', limit=1)

        if not line:
            raise ValidationError(
                f"La variable económica '{code}' no tiene valores configurados para el año {year}. "
                f"Por favor, defina los valores para poder continuar."
            )

        if variable.code not in ('TRTEFTE', 'FSOL', 'FSUB'):
            return line.value
        else:
            table = []
            for detail in line.variable_line_detail_ids:
                table.append({
                    'subtract': detail.subtract,
                    'rate': detail.rate,
                    'add': detail.add,
                    'lower_limit': detail.lower_limit if detail.has_lower_limit else None,
                    'upper_limit': detail.upper_limit if detail.has_upper_limit else None
                })
            return table

    @api.model
    def get_values_by_date(self, dates_with_codes):
        """
        Retrieves the values for a list of economic variable codes for specific dates.

        :param dates_with_codes: A dictionary where keys are dates (datetime.date)
                                 and values are lists of variable codes (str).
                                 e.g., {date1: ['codeA', 'codeB'], date2: ['codeA']}
        :return: A dictionary structured as {code: {(year, month): value}}.
                 The value can be a float or a list of dictionaries (table).
        """
        all_codes = set(
            code for codes in dates_with_codes.values() for code in codes)
        results = {code: {} for code in all_codes}

        for date_ref, codes in dates_with_codes.items():
            key = (date_ref.year, date_ref.month)
            for code in codes:
                if key not in results[code]:
                    value = self.get_value_by_date(code, date_ref)
                    results[code][key] = value
        return results
