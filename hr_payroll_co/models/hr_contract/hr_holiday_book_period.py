# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrHolidayBookPeriod(models.Model):
    _name = 'hr.holiday.book.period'
    _description = 'Libro de vacaciones por periodo'

    contract_id = fields.Many2one(
        comodel_name='hr.contract', string='Contrato', required=True)
    date_from = fields.Date(string="Fecha inicial")
    date_to = fields.Date(string="Fecha final")
    days_worked = fields.Float(string="Días trabajados", default=0)
    days_suspension = fields.Float(string='Días suspendidos', default=0)
    days_accrued = fields.Float(string="Días causados", default=0)
    days_payroll = fields.Float(string="Días en nómina", default=0)
    days_enjoyed = fields.Float(string="Días disfrutados", default=0)
    days_validated = fields.Float(string="Días validados", default=0)
    days_paid = fields.Float(string="Días pagados", default=0)
    days_pending = fields.Float(string="Días pendientes", default=0)
    date_start_vacation = fields.Date(string="Día inicio vacaciones")
    date_end_vacation = fields.Date(string="Día final vacaciones")
    leave_id = fields.Many2one(
        comodel_name='hr.leave', string='Ausencia')
