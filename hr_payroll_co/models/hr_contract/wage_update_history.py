# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import datetime

LAST_ONE = -1


class WageUpdateHistory(models.Model):
    _name = 'wage.update.history'
    _order = 'date desc'
    _rec_name = "date"
    _description = 'Histórico de Cambios de Salario'

    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract', required=True)
    wage = fields.Float(
        string='Salario', required=True)
    date = fields.Date(
        string='Fecha', default=fields.Date.today(), required=True)
    user_id = fields.Many2one(string='Responsable', comodel_name='res.users',
                              default=lambda self: self.env.user,
                              required=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)
    appy_retroactive = fields.Boolean(
        string='Aplica Retroactivo')
    date_retroactive_from = fields.Date(
        string='Fecha Retroactivo')
    retroactive_novelty_id = fields.Many2one(
        'hr.novelty', string='Novedad de Retroactividad')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'appy_retroactive' in vals and 'date_retroactive_from' in vals:
                if vals.get('appy_retroactive'):
                    vals['retroactive_novelty_id'] = self._create_retroactive_novelty(vals['date_retroactive_from'], vals, True)
        res = super(WageUpdateHistory, self).create(vals_list)
        for vals in vals_list:
            contract_id = vals.get('contract_id', False)
            histories = self.search([('contract_id', '=', contract_id)]).sorted(
                lambda hist: hist.date)
            wage = histories[LAST_ONE].wage if histories else vals.get('wage', 0.0)
            self.env['hr.contract'].browse([contract_id]).write(
                {'wage': wage})
        return res

    def write(self, vals):
        if 'appy_retroactive' in vals:
            if vals['appy_retroactive'] is False:
                vals['date_retroactive_from'] = False
                if self.retroactive_novelty_id.state == 'paid':
                    raise ValidationError('Esta línea no se puede desmarcar de retroactivo, tiene una novedad asociada pagada.')
                self.retroactive_novelty_id.to_draft()
                self.retroactive_novelty_id.unlink()
            if (vals['appy_retroactive'] is True and (vals.get('date_retroactive_from') or self.date_retroactive_from)):
                date_from = vals.get('date_retroactive_from') or self.date_retroactive_from
                vals['retroactive_novelty_id'] = self._create_retroactive_novelty(date_from, vals)
        if (vals.get('wage') or vals.get('date') or vals.get('date_retroactive_from')) and self.appy_retroactive:
            date_from = vals.get('date_retroactive_from') or self.date_retroactive_from
            vals['retroactive_novelty_id'] = self._create_retroactive_novelty(date_from, vals)
        return super().write(vals)

    @api.constrains('appy_retroactive', 'date_retroactive_from')
    def _check_retroactive_data(self):
        for record in self:
            pass

    @api.onchange('appy_retroactive')
    def _onchange_appy_retroactive(self):
        for record in self:
            if not record.appy_retroactive:
                record.date_retroactive_from = False

    def _create_retroactive_novelty(self, date_from, vals, create=False):
        discount_leave_days_in_retroactive = self.env['ir.config_parameter'].sudo().get_param(
            'hr_payroll_co.discount_leave_days_in_retroactive')
        exclued_dates = []
        if not create:
            novelty = self.retroactive_novelty_id
            if novelty.state == 'paid':
                return novelty.id
        else:
            novelty = False
        default_category = self.env['hr.novelty.type'].search([
            ('use_by_default_retroactive', '=', True)], limit=1)
        if not default_category:
            raise ValidationError("No se ha encontrado una categoría de novedad"
                                  " marcada con 'Usar por defecto en novedades generadas automaticas en retroactivos'")
        if vals.get('contract_id'):
            contract = self.env['hr.contract'].browse(vals.get('contract_id'))
        else:
            contract = self.contract_id
        date = vals.get('date') or self.date
        wage = vals.get('wage') or self.wage
        period_reference = self.env['hr.period'].search([
            ('start', '<=', date),
            ('end', '>=', date),
            ('type_period', '=', contract.schedule_pay),
            ('company_id', '=', contract.company_id.id)
        ], limit=1)
        if period_reference:
            paid_periods = self.env['hr.payslip'].search([
                ('period_id.start', '>=', period_reference.start),
                ('contract_id', '=', contract.id),
                ('state', '=', 'paid'),
                ('payslip_type_id.category', '=', 'NOM')
            ], order='id desc', limit=1)
            if paid_periods:
                retroactive_amount = 0
                amount_by_day = wage / 30
                if type(date) == str:
                    date_start = datetime.strptime(date, '%Y-%m-%d').date()
                else:
                    date_start = date
                date_to = paid_periods.period_id.end
                if discount_leave_days_in_retroactive:
                    exclued_dates += [x.date for x in contract.get_days_leave(date_start, date_to)]
                if paid_periods.period_id.type_period == 'BIWEEKLY' and paid_periods.period_id.type_biweekly == 'FIRST':
                    # Exclude days from the second half of the month up to day 30.
                    exclude_date = paid_periods.period_id.end + relativedelta(days=1)
                    max_day = min(30, (paid_periods.period_id.end + relativedelta(day=31)).day)
                    while exclude_date.month == paid_periods.period_id.end.month and exclude_date.day <= max_day:
                        exclued_dates.append(exclude_date)
                        exclude_date += relativedelta(days=1)
                salaries = contract.average_wage_history_by_days(date_start, date_to, [self.id], exclued_dates)
                for salary in salaries.values():
                    for day_salary in salary.values():
                        retroactive_amount += amount_by_day - day_salary
                vals = {
                    'contract_id': contract.id,
                    'approve_date': date_from,
                    'date_start': date_from,
                    'company_id': contract.company_id.id,
                    'amount': retroactive_amount,
                    'novelty_type_id': default_category.id,
                    'employee_id': contract.employee_id.id,
                }
                if not novelty:
                    novelty = self.env['hr.novelty'].create(vals)
                else:
                    novelty.to_draft()
                    novelty.write(vals)
                novelty.to_confirm()
                novelty.to_validated()
            return novelty.id
        return False

    def unlink(self):
        for record in self.filtered(
                lambda x: x.retroactive_novelty_id):
            if record.retroactive_novelty_id.state == 'paid':
                raise ValidationError('Esta línea no se puede eliminar, tiene una novedad asociada pagada.')
            record.retroactive_novelty_id.to_draft()
            record.retroactive_novelty_id.unlink()
        return super().unlink()
