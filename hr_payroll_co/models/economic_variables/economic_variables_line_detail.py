from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class EconomicVariablesLineDetail(models.Model):
    _name = 'economic.variable.line.detail'
    _description = 'Detalle de línea de variable económica'
    _order = 'id'

    variable_line_id = fields.Many2one(
        comodel_name='economic.variable.line', string='Línea de variable económica')
    subtract = fields.Float(string='UVTs a Restar')
    rate = fields.Float(string='Porcentaje')
    add = fields.Float(string='UVTs a Sumar')

    lower_limit = fields.Float(string='Límite inferior')
    has_lower_limit = fields.Boolean(
        string='Tiene límite inferior', default=True)
    upper_limit = fields.Float(string='Límite superior')
    has_upper_limit = fields.Boolean(
        string='Tiene límite superior', default=True)
    variable_code = fields.Char(string='Código de Variable')

    @api.onchange('has_lower_limit')
    def _onchange_has_lower_limit(self):
        if not self.has_lower_limit:
            self.lower_limit = 0

    @api.onchange('has_upper_limit')
    def _onchange_has_upper_limit(self):
        if not self.has_upper_limit:
            self.upper_limit = 0

    @api.constrains('lower_limit', 'upper_limit')
    def _check_limits(self):
        for record in self:
            if record.lower_limit >= record.upper_limit and record.has_lower_limit and record.has_upper_limit:
                message = f"El límite inferior {record.lower_limit} "
                message += f"debe ser menor al límite superior {record.upper_limit}"
                raise ValidationError(message)
