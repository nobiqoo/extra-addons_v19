# -*- coding: utf-8 -*-
from odoo import fields, models


class HourlyScheduleUpdateHistory(models.Model):
    _name = 'hourly.schedule.update.history'
    _order = 'date desc'
    _rec_name = 'date'
    _description = 'Histórico de Cambios de Jornada de Trabajador por Horas'

    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract', required=True, domain="[('is_hourly_worker','=',True)]")
    monthly_hours = fields.Float(
        string='Número de Horas Mensuales', required=True,
        help='Horas mensuales usadas para calcular el valor hora: Salario / Horas Mensuales.')
    daily_hours = fields.Float(
        string='Número de Horas Diarias', required=True,
        help='Horas diarias usadas para calcular el valor de un día ordinario laborado: '
             'Valor Hora x Horas Diarias.')
    date = fields.Date(
        string='Fecha', default=fields.Date.today(), required=True)
    user_id = fields.Many2one(
        string='Responsable', comodel_name='res.users',
        default=lambda self: self.env.user, required=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)
