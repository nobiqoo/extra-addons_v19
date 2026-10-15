# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HourValueUpdateHistory(models.Model):
    _name = 'hour.value.update.history'
    _order = 'date desc'
    _rec_name = 'date'
    _description = 'Histórico de Valor Hora'

    contract_id = fields.Many2one(
        comodel_name='hr.contract', string='Contrato', required=True,
        ondelete='cascade')
    date = fields.Date(
        string='Fecha de Inicio', required=True,
        default=fields.Date.context_today,
        help='Fecha desde la cual rige este valor hora.')
    hour_value = fields.Float(
        string='Valor Hora', required=True)
    user_id = fields.Many2one(
        comodel_name='res.users', string='Responsable',
        default=lambda self: self.env.user, required=True, readonly=True)
    company_id = fields.Many2one(
        comodel_name='res.company', string='Compañía',
        default=lambda self: self.env.company, index=True, required=True)

    _contract_date_uniq = models.Constraint(
        'UNIQUE (contract_id, date)',
        'Ya existe un valor hora registrado para esa fecha en el contrato.',
    )

    @api.constrains('hour_value')
    def _check_hour_value(self):
        for record in self:
            if record.hour_value <= 0:
                raise ValidationError(
                    'El valor hora debe ser mayor a cero.')
