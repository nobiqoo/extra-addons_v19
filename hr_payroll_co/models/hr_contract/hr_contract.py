# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from datetime import datetime, date, timedelta
from odoo.addons.utilities_collection.time import days360
from ..hr_payslip_period.hr_period import TYPE_PERIOD
from datetime import timedelta
from collections import defaultdict
from calendar import monthrange

from types import SimpleNamespace
from odoo.fields import Date
import base64
import io
import xlsxwriter


CONTRACT_GROUP_ID_HELP = """
Este campo permite agrupar los contratos, según se va a calcular la nómina.
Sirve para grupos que no sea por banco, centro de costo y/o ciudad de desempeño.
"""
ARL_ID_HELP = "ARL en el caso que el empleado sea independiente"
ANALYTIC_DISTRIBUTION_TOTAL_WARN = """: La suma de las distribuciones analíticas debe ser 100.0%%,
Valor actual: %s%%"""
CONTRACT_EXTENSION_NO_RECORD_WARN = """
Para prorrogar el contrato por favor registre una prorroga
"""
CONTRACT_EXTENSION_MAX_WARN = """
No es posible realizar una prórroga por un periodo inferior
a un año despues de tener 3 o más prórrogas
"""
NO_PARTNER_REF_WARN = """
No se encontró el numero de documento en el contacto
"""
IN_FORCE_CONTRACT_WARN = """
El empleado yá tiene un contrato activo: %s.
"""

NO_WAGE_HISTORY = """
El contrato %s no tiene un historial de salarios.
"""

MANY_WAGE_HISTORY = """
El contrato %s tiene %s cambios salariales en este rango %s a %s.
Solo se permite 1 por periodo.
"""

LAST_ONE = -1

SETTLEMENT_TYPE_SELECTION = [
    ('vol', 'Retiro Voluntario del Trabajador'),
    ('lab', 'Terminación de la Labor Contratada'),
    ('causa', 'Cancelación por Justa Causa'),
    ('prueba', 'Terminación del Contrato en Periodo de Prueba'),
    ('n_causa', 'Retiro sin Justa Causa'),
    ('exp', 'Expiración Plazo Fijo Pactado'),
    ('unil', 'Decisión Unilateral de la Compañía'),
    ('fal', 'Fallecimiento'),
    ('pen', 'Pensionado'),
    ('nolab', 'No Laboró'),
    ('mutuo', 'Terminación Mutuo Acuerdo')
]


class HRContract(models.Model):
    _name = 'hr.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Contrato laboral del empleado'
    _order = 'name'

    name = fields.Char(string='Contrato',
                       required=True, default='- NUEVO CONTRATO -')
    active = fields.Boolean(string='Activo', default=True)
    kanban_state = fields.Selection(
        [
            ('normal', 'Normal'),
            ('blocked', 'Blocked'),
            ('done', 'Done'),
        ],
        string='Kanban State',
        default='normal',
        copy=False,
        required=False,
    )
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    company_id = fields.Many2one('res.company', related='employee_id.company_id', store=True, readonly=False,
                                 default=lambda self: self.env.company, required=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('open', 'En progreso'),
        ('close', 'Terminado'),
        ('cancel', 'Cancelado')
    ], string='Estado', copy=False, tracking=True, default='draft')
    notes = fields.Html('Notes')
    risk_id = fields.Many2one(string='Riesgo', comodel_name='hr.contract.risk')
    risk_percentage = fields.Float(
        string='Porcentaje de Riesgo', related='risk_id.risk_percentage', digits=(16, 6))
    high_risk = fields.Boolean(string='Alto Riesgo')
    contract_city_id = fields.Many2one(
        string='Ciudad de Contrato', comodel_name='res.city')
    work_city_id = fields.Many2one(
        string='Ciudad de Desempeño', comodel_name='res.city')
    contract_group_id = fields.Many2one(
        string='Grupo de Contrato', comodel_name='hr.contract.group',
        help=CONTRACT_GROUP_ID_HELP, tracking=True)
    contract_type_id = fields.Many2one(
        string='Tipo de Contrato', comodel_name='hr.contract.type',
        tracking=True)
    job_id = fields.Many2one(string='Título del Cargo', comodel_name='hr.job')
    term = fields.Selection(string='Termino',
                            related="contract_type_id.term", store=True)
    eps_id = fields.Many2one(
        string='EPS', comodel_name='res.partner', domain="[('eps','=','True')]")
    eps_history_ids = fields.One2many(
        string='Histórico EPS', comodel_name='eps.update.history',
        inverse_name='contract_id')
    afp_pension_id = fields.Many2one(
        string='Fondo de Pensiones', comodel_name='res.partner', domain="[('afp','=','True')]")
    pension_history_ids = fields.One2many(
        string='Histórico Fondo de Pensiones', comodel_name='pension.update.history',
        inverse_name='contract_id')
    afp_severance_id = fields.Many2one(
        string='Fondo de Cesantías', comodel_name='res.partner', domain="[('afp','=','True')]")
    severance_history_ids = fields.One2many(
        string='Histórico Fondo de Cesantías', comodel_name='severance.update.history',
        inverse_name='contract_id')
    arl_id = fields.Many2one(
        string='ARL', comodel_name='res.partner',
        domain="[('arl','=','True')]", help=ARL_ID_HELP)
    ccf_id = fields.Many2one(
        string='CCF', comodel_name='res.partner',
        domain="[('ccf','=','True')]")

    # Salario y Beneficios
    currency_id = fields.Many2one(
        string='Moneda', comodel_name='res.currency', default=lambda self: self.env.company.currency_id)
    wage = fields.Monetary(
        'Salario', help="Employee's monthly gross wage.", readonly=True, aggregator="avg")
    wage_history_ids = fields.One2many(
        string='Histórico Salario', comodel_name='wage.update.history',
        inverse_name='contract_id')
    bonus = fields.Monetary(string='Bono')
    fiscal_type_id = fields.Many2one(
        string='Tipo de Cotizante', comodel_name='hr.fiscal.type',
        tracking=True)
    fiscal_subtype_id = fields.Many2one(
        string='Subtipo de Cotizante', comodel_name='hr.fiscal.subtype',
        tracking=True)
    skip_commute_allowance = fields.Boolean(
        string='Omitir Auxilio de Transporte')
    remote_work_allowance = fields.Boolean(
        string='Aplica Auxilio de Conectividad')
    apply_day31_benefit = fields.Boolean(
        string='Aplica beneficio día 31', default=False, tracking=True,
        help='Genera automáticamente las novedades de día 31 de salario y de '
             'subsidio de transporte al calcular la nómina de un periodo que '
             'termina el día 31.')
    minimum_wage = fields.Boolean(
        string='Devenga Salario Mínimo')
    limit_deductions = fields.Boolean(
        string='Limitar Deducciones al 50% de Devengos')
    workcenter = fields.Char(string='Centro de Trabajo')

    # Horario
    resource_calendar_id = fields.Many2one('resource.calendar', 'Horario laboral', required=True,
                                           domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    # Duración

    date_start = fields.Date('Fecha de inicio')
    date_end = fields.Date('Fecha fin')
    trial_date_start = fields.Date(string='Periodo de Prueba')
    trial_date_end = fields.Date(string='Fin de Periodo de Prueba')
    contract_days = fields.Integer(string='Días de Contrato')
    schedule_pay = fields.Selection(
        string='Categoría', selection=TYPE_PERIOD, default='MONTHLY', required=True)
    apprentice_to_worker_date = fields.Date(
        string='Fecha de Cambio a Etapa Productiva')

    # Liquidación

    settlement_date = fields.Date(string='Fecha de liquidación')
    settlement_period_id = fields.Many2one(
        string='Periodo de liquidación', comodel_name='hr.period')
    settlement_type = fields.Selection(
        string='Tipo de finalización', selection=SETTLEMENT_TYPE_SELECTION)

    # Deducciones

    deduction_dependents = fields.Boolean(string='Dependientes')
    deduction_by_estate = fields.Monetary(
        string='Deducción por Interes de Vivienda')
    deduction_by_healthcare = fields.Monetary(
        string='Deducción por Medicina Prepagada')
    deduction_by_icetex = fields.Monetary(
        string='Deducción por Intereses de ICETEX')

    # Contabilidad

    journal_id = fields.Many2one(
        string='Libro de Salarios', comodel_name='account.journal')
    analytic_distribution_ids = fields.One2many(
        string='Distribuciones Analíticas',
        comodel_name='hr.contract.analytic.distribution',
        inverse_name='contract_id')

    analytic_distribution = fields.Json(
        string='Distribución Analítica',
    )

    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get(
            "Percentage Analytic"),
    )

    analytic_distribution_contract = fields.Boolean(
        related='company_id.analytic_distribution_contract'
    )

    cecos_analytic_id = fields.Many2one(
        string='Cecos Principal',
        comodel_name='account.analytic.account')

    # Dotaciones

    equipment_ids = fields.One2many(
        string='Dotaciones', comodel_name='hr.equipment',
        inverse_name='contract_id')

    # Historial de Nominas

    paysplip_ids = fields.One2many(
        string='Historial de Nominas', comodel_name='hr.payslip',
        inverse_name='contract_id')

    # Procedimiento 2

    apply_procedure_2 = fields.Boolean(string='Aplicar Procedimiento 2')
    withholding_percent = fields.Float(string='Porcentaje de Retención')
    withholding_log_ids = fields.One2many(
        string='Calculo de Rete-Fuente Procedimiento 2',
        comodel_name='hr.contract.withholding.log', inverse_name='contract_id')

    # Prorrogas

    contract_extension_ids = fields.One2many(
        string='Prórrogas',
        comodel_name='hr.contract.extension', inverse_name='contract_id')

    # Novedades

    contract_novelty_ids = fields.One2many(
        string='Novedades',
        comodel_name='hr.contract.novelty', inverse_name='contract_id')

    # Smart buttons

    novelty_count = fields.Integer(
        string='Total Novedades', compute='_compute_payslip_novelty_counts')
    leave_count = fields.Integer(
        string='Total Ausencias', compute='_compute_payslip_novelty_counts')
    overtime_count = fields.Integer(
        string='Total Horas Extras', compute='_compute_payslip_novelty_counts')

    def _compute_payslip_novelty_counts(self):
        counts = {
            'novelty_count': ('hr.novelty', {}),
            'leave_count': ('hr.leave', {}),
            'overtime_count': ('hr.overtime', {}),
        }
        for field_name, (model, data) in counts.items():
            grouped = self.env[model]._read_group(
                [('contract_id', 'in', self.ids)],
                groupby=['contract_id'], aggregates=['__count'])
            data.update({contract.id: count for contract, count in grouped})
        for contract in self:
            for field_name, (model, data) in counts.items():
                contract[field_name] = data.get(contract.id, 0)

    def _action_view_payslip_novelties(self, name, model):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {
                'default_contract_id': self.id,
                'default_employee_id': self.employee_id.id,
            },
        }

    def action_view_novelties(self):
        return self._action_view_payslip_novelties('Novedades', 'hr.novelty')

    def action_view_leaves(self):
        return self._action_view_payslip_novelties('Ausencias', 'hr.leave')

    def action_view_overtimes(self):
        return self._action_view_payslip_novelties('Horas Extras', 'hr.overtime')

    # Libro de vacaciones

    holiday_book_ids = fields.One2many(
        comodel_name='hr.holiday.book', inverse_name='contract_id', string='Libro de vacaciones')
    holiday_book_period_ids = fields.One2many(
        comodel_name='hr.holiday.book.period', inverse_name='contract_id', string='Libro de vacaciones por periodo')
    days_left = fields.Float(string='Días restantes', default=0, readonly=True)
    date_ref_holiday_book = fields.Date(string='Fecha referencia')

    # Reportes
    worked_days = fields.Float(
        string='Días Trabajados'
    )

    is_conventional = fields.Boolean(
        string='Convención',
        default=False
    )
    room_prima_amount = fields.Float(
        string='Prima de Habitación'
    )

    # Locación

    location_code = fields.Char(
        string='Código de localización', compute='_compute_location_code', store=True)

    # Reforma pensional
    is_transitional_regime = fields.Boolean(
        'Régimen de transición', default=False)

    # Proceso Disciplinario
    disciplinary_ids = fields.One2many(
        'hr.contract.disciplinary.line',
        'contract_id',
        string='Procesos Disciplinarios'
    )


    def _get_contract_name(self, employee_id):
        contracts = self.env['hr.contract'].search([
            ('employee_id', '=', employee_id)
        ])
        employee = self.env['hr.employee'].browse([employee_id])
        vat = employee.partner_id.vat
        if not vat:
            raise ValidationError(NO_PARTNER_REF_WARN)
        contract_number = 'C' + str(len(contracts) + 1).rjust(2, '0')
        return vat + ' - ' + contract_number

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            employee_id = vals.get('employee_id', False)
            vals['name'] = self._get_contract_name(employee_id)
            contracts = self.env['hr.contract'].search([
                ('employee_id', '=', employee_id),
                ('state', 'in', ['draft', 'open'])
            ])

            if contracts:
                raise ValidationError(
                    IN_FORCE_CONTRACT_WARN % contracts[0].name)
        return super(HRContract, self).create(vals_list)

    @api.onchange('eps_history_ids', 'pension_history_ids', 'severance_history_ids')
    @api.constrains('eps_history_ids', 'pension_history_ids', 'severance_history_ids')
    def _update_social_security_from_history(self):
        for contract in self:
            if contract.eps_history_ids:
                contract.eps_id = contract.eps_history_ids.sorted(
                    lambda hist: hist.date)[LAST_ONE].eps_id
            if contract.pension_history_ids:
                contract.afp_pension_id = contract.pension_history_ids.sorted(
                    lambda hist: hist.date)[LAST_ONE].afp_pension_id
            if contract.severance_history_ids:
                contract.afp_severance_id = contract.severance_history_ids.sorted(
                    lambda hist: hist.date)[LAST_ONE].afp_severance_id

    @api.onchange('wage_history_ids')
    @api.constrains('wage_history_ids')
    def _update_wage_from_history(self):
        for contract in self:
            if contract.wage_history_ids:
                contract.wage = contract.wage_history_ids.sorted(
                    lambda hist: hist.date)[LAST_ONE].wage

    @api.constrains('date_start')
    def _compute_trial_period(self):
        trial_months = 2
        trial_time = relativedelta(months=trial_months) - relativedelta(days=1)
        for contract in self:
            if not contract.date_start:
                raise ValidationError(
                    'El contrato debe tener una fecha de inicio')
            contract.trial_date_start = contract.date_start
            contract.trial_date_end = contract.date_start + trial_time

    @api.depends('company_id.chart_template')
    def _compute_location_code(self):
        for record in self:
            record.location_code = record.company_id.chart_template

    @api.constrains('analytic_distribution_ids')
    def _check_analytic_distribution_sum(self):
        for contract in self:
            total = sum(
                [adst.rate for adst in contract.analytic_distribution_ids])
            if contract.company_id.allow_analytic_distribution_over_100 and total > 100.0:
                continue
            if 0.0 != total != 100.0:
                raise ValidationError(contract.name +
                                      ANALYTIC_DISTRIBUTION_TOTAL_WARN % total)

    def extend_contract(self):
        """Extend contract end date"""
        max_extensions, min_days = 3, 360
        for contract in self:
            if not contract.contract_extension_ids:
                raise ValidationError(CONTRACT_EXTENSION_NO_RECORD_WARN)
            last_extension = contract.contract_extension_ids.sorted(
                key=lambda r: r.sequence)[LAST_ONE]
            contract.date_end = last_extension.date_to
            if len(contract.contract_extension_ids) <= max_extensions:
                continue
            extension_span_days = days360(
                last_extension.date_from, last_extension.date_to)
            if extension_span_days < min_days:
                raise ValidationError(CONTRACT_EXTENSION_MAX_WARN)

    def get_wage(self, date_end, date_start=False):
        """
        Obtiene el salario en determinada fecha
        @return:
            dict -> {fecha, salario, salario_anterior}
        """
        if not self.wage_history_ids:
            raise ValidationError(NO_WAGE_HISTORY % self.name)
        if date_start:
            salary = list(filter(
                lambda x: date_start <= x.date <= date_end, self.wage_history_ids))
            if not salary:
                return self.get_wage(date_end)
            elif len(salary) > 1:
                raise ValidationError(MANY_WAGE_HISTORY % (
                    self.name, len(salary), date_start, date_end))
            elif date_start <= self.date_start <= date_end:
                return {'wage': salary[0].wage}
            last = self.get_wage(salary[0].date - timedelta(days=1))
            return {'date': salary[0].date, 'wage': salary[0].wage, 'last_wage': last['wage']}
        salary = list(filter(
            lambda x: x.date <= date_end, self.wage_history_ids))
        if not salary:
            raise ValidationError(
                (NO_WAGE_HISTORY + 'Para esta fecha %s') % (self.name, date_end))
        salary = max(salary, key=lambda x: x.date)
        return {'wage': salary.wage}

    def average_wage_history(self, date_from, date_to):
        ranges = {}
        months = {}
        while date_from < date_to:
            init_date, last_day = self.get_month_last_day(date_from)
            if last_day > date_to:
                date_to = last_day
            ranges[date_from.month] = {
                'date_from': init_date,
                'date_to': last_day,
                'salaries': {}
            }
            date_from = last_day + relativedelta(days=1)
        for key, vals in ranges.items():
            total_value = 0
            days_values = {}
            days_qty = days360(vals['date_from'], vals['date_to'])
            count_days = 1
            last_wage = False
            date_from, date_to = vals['date_from'], vals['date_to']
            while date_from <= date_to:
                if count_days > days_qty:
                    break
                salary = self.wage_history_ids.filtered(
                    lambda x: x.date <= date_from)[0]
                if not last_wage:
                    last_wage = salary
                if last_wage.id != salary:
                    last_wage = salary
                if date_from.month not in days_values.keys():
                    days_values[date_from.month] = {
                        count_days: salary.wage
                    }
                else:
                    days_values[date_from.month][count_days] = salary.wage
                total_value += salary.wage
                date_from += relativedelta(days=1)
                count_days += 1
            if count_days - 1 <= 30 and vals['date_from'].month == 2:
                total_value += salary.wage * (30 - (count_days - 1))
            months[vals['date_from'].month] = total_value / \
                days_qty if days_qty != 0 else 0
        return months

    def average_wage_history_by_days(self, date_from, date_to, excludes=[], date_excludes=[]):
        ranges = {}
        months = {}
        days_values = {}
        while date_from < date_to:
            init_date, last_day = self.get_month_last_day(date_from)
            if last_day > date_to:
                date_to = last_day
            ranges[date_from.month] = {
                'date_from': init_date,
                'date_to': last_day,
                'salaries': {}
            }
            date_from = last_day + relativedelta(days=1)
        for key, vals in ranges.items():
            total_value = 0
            days_qty = days360(vals['date_from'], vals['date_to'])
            count_days = 1
            last_wage = False
            date_from, date_to = vals['date_from'], vals['date_to']
            while date_from <= date_to:
                if date_from in date_excludes:
                    count_days += 1
                    date_from += relativedelta(days=1)
                    continue
                if count_days > days_qty:
                    break
                salary = self.wage_history_ids.filtered(
                    lambda x: x.date <= date_from and x.id not in excludes)[0]
                if not last_wage:
                    last_wage = salary
                if last_wage.id != salary:
                    last_wage = salary
                if date_from.month not in days_values.keys():
                    days_values[date_from.month] = {
                        count_days: salary.wage / 30
                    }
                else:
                    days_values[date_from.month][count_days] = salary.wage / 30
                total_value += salary.wage
                date_from += relativedelta(days=1)
                count_days += 1
            if vals['date_from'].month == 2 and date_from.month == 3 and date_from.day == 1:
                days_values[vals['date_from'].month][count_days] = salary.wage / 30
                if count_days < 30:
                    days_values[vals['date_from'].month][30] = salary.wage / 30
            if count_days - 1 <= 30 and vals['date_from'].month == 2:
                total_value += salary.wage * (30 - (count_days - 1))
            months[vals['date_from'].month] = total_value / \
                days_qty if days_qty != 0 else 0
        return days_values

    def get_month_last_day(self, date):
        next_month = date.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        if self.settlement_date and self.settlement_date.month == last_day.month and self.settlement_date < last_day:
            last_day = self.settlement_date
        return date, last_day

    def liquidate_contract(self):
        payslips_liq = []
        payslip_type = self.env['hr.payslip.type'].search(
            [('category', '=', 'LIQ')], limit=1)
        if not payslip_type:
            raise ValidationError(
                'No se encontró la categoría de nómina de categoría liquidación.')
        for record in self:
            message = 'El contrato %s no tiene ' % record.name
            if record.state != 'open':
                continue
            elif not record.settlement_date:
                raise ValidationError(message + 'fecha de liquidación.')
            elif not record.settlement_period_id:
                raise ValidationError(message + 'periodo de liquidación.')
            elif not record.settlement_type:
                raise ValidationError(message + 'tipo de finalización.')
            elif not record.journal_id:
                raise ValidationError(message + 'libro de salarios.')

            payslips_liq.append({
                'state': 'draft',
                'contract_id': record.id,
                'employee_id': record.employee_id.id,
                'liquidation_date': record.settlement_date,
                'accounting_date': record.settlement_date,
                'company_id': record.company_id.id,
                'period_id': record.settlement_period_id.id,
                'payslip_type_id': payslip_type.id,
                'journal_id': record.journal_id.id,
            })
            record.state = 'close'
        payslips_liq_ids = self.env['hr.payslip'].create(payslips_liq)
        error_message = payslips_liq_ids.compute_slip(self._cr)
        if error_message:
            raise ValidationError(error_message)
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'list,form',
            'res_model': 'hr.payslip',
            'target': 'current',
            'context': {},
            'domain': [('id', 'in', payslips_liq_ids.ids)],
        }

    def has_change_salary(self, date_from, date_to):
        wages_in_period = filter(
            lambda x: date_from <= x.date <= date_to, self.wage_history_ids)
        return len(list(wages_in_period)) >= 1

    def get_rest_days_payable(self):
        '''
        Calculate the amount of rest days to be paid for a full day worked in the settlement.
        return int
        '''
        if not self.settlement_date:
            return 0

        working_days = {int(x.dayofweek)
                        for x in self.resource_calendar_id.attendance_ids}
        if not working_days:
            return 0

        contract_days = days360(self.date_start, self.settlement_date)
        if contract_days < len(working_days):
            return 0

        rest_days_payable = 0
        next_date = self.settlement_date + timedelta(days=1)
        while next_date.weekday() not in working_days:
            if next_date.day == 31:
                break
            rest_days_payable += 1
            next_date += timedelta(days=1)
        return rest_days_payable

    def is_rest_day(self, date):
        work_days = {
            int(work_day.dayofweek)
            for work_day in self.resource_calendar_id.attendance_ids
        }
        return date.weekday() not in work_days

    def get_ibc_previous(self, date, smmlv, vac_smmlv=False, exclude_vac_money=False):
        date_from = date.replace(day=1) - relativedelta(months=1)
        date_to = date_from.replace(day=monthrange(
            date_from.year, date_from.month)[1])
        period = {'start': date_from, 'end': date_to}

        categories = ('earnings', 'o_salarial_earnings',
                      'comp_earnings', 'o_rights', 'o_earnings')
        exclude = ('PRIMA', 'PRIMA_LIQ', 'VAC_LIQ')

        categories_amounts = {}
        self.env['hr.concept']._get_total_concept_categories(
            self._cr, categories_amounts, period, self.id, categories=categories, exclude=exclude)

        non_salarial = categories_amounts.get('o_earnings', 0)
        salarial = sum(categories_amounts.values()) - non_salarial

        if exclude_vac_money:
            domain = [('state', 'in', ('validated', 'paid')),
                      ('date', '>=', period['start']),
                      ('date', '<=', period['end']),
                      ('contract_id', '=', self.id),
                      ('leave_id.category_type', '=', 'VAC_MONEY')]
            vac_money_amount = sum(
                self.env['hr.leave.line'].search(domain).mapped('amount'))
            salarial -= vac_money_amount

        tope40 = (salarial + non_salarial) * 0.4
        if non_salarial > tope40:
            amount = salarial + non_salarial - tope40
        else:
            amount = salarial

        if amount == 0:
            amount = self.get_wage(date)['wage']

        if self.contract_type_id.type_class == 'int':
            amount *= 0.7

        if amount > 25 * smmlv:
            amount = 25 * smmlv

        if amount < smmlv and vac_smmlv:
            return smmlv

        return amount

    ##########################
    ###### HOLYDAY BOOK ######
    ##########################

    def get_benefits_days_base(self):
        """Días del año sobre los que se causan las prestaciones sociales
        (cesantías, intereses, prima y vacaciones). Por ley son 360; un
        módulo de cliente puede sobrescribirlo para pactar otra base."""
        return 360

    def get_holiday_book(self, data_payslip, date_ref=False):
        date_start = self.date_start
        date_ref = date_ref or self.date_ref_holiday_book or datetime.now()

        if self.fiscal_type_id.code in ('12', '19', '23'):
            hr_concept = self.env['hr.concept']
            period_id = self.env['hr.period'].get_period(
                date_ref, None, self.schedule_pay)
            if not hr_concept._apply_labor_reform({'period': period_id, 'politics': data_payslip['politics']}) or self.fiscal_type_id.code in ('12', '23'):
                return {
                    'worked_days': 0,
                    'days_left': 0,
                    'days_enjoyed': 0,
                    'days_paid': 0,
                    'days_suspension': 0,
                }
            else:
                if hr_concept.get_labor_reform_start_date() > date_start:
                    date_start = hr_concept.get_labor_reform_start_date()

                # La etapa lectiva no causa vacaciones
                if self.apprentice_to_worker_date and self.apprentice_to_worker_date > date_start:
                    date_start = self.apprentice_to_worker_date

        worked_days = days360(date_start, date_ref)
        days_enjoyed, days_paid, days_suspension = 0, 0, 0
        for holiday_book in self.holiday_book_ids:
            days_enjoyed += holiday_book.days_enjoyed
            days_paid += holiday_book.days_paid
            days_suspension += holiday_book.days_suspension
        worked_days -= days_suspension
        days_left = (worked_days * 15 / self.get_benefits_days_base()) - \
            (days_enjoyed + days_paid)
        return {
            'worked_days': worked_days,
            'days_left': days_left,
            'days_enjoyed': days_enjoyed,
            'days_paid': days_paid,
            'days_suspension': days_suspension,
        }

    def update_days_left(self):
        dont_apply_labor_reform = self.env['ir.config_parameter'].sudo().get_param('hr_payroll_co.dont_apply_labor_reform')
        data_payslip = {
            'politics': {'hr_payroll_co.dont_apply_labor_reform': dont_apply_labor_reform},
            'contract': self
        }
        self.days_left = self.get_holiday_book(data_payslip)['days_left']
        self._calculate_holiday_book_period()

    def add_to_holiday_book(self, payslip_id):
        holidays = defaultdict(list)
        money_holidays = defaultdict(list)
        suspension_days = defaultdict(list)

        leave_lines_ids = self.env['hr.leave.line'].search([
            ('payslip_id', '=', payslip_id.id)
        ])

        for ll in filter(lambda ll: ll.leave_id.category_type == 'VAC', leave_lines_ids):
            holidays[ll.leave_id].append(ll)

        for ll in filter(lambda ll: ll.leave_id.category_type == 'VAC_MONEY', leave_lines_ids):
            money_holidays[ll.leave_id].append(ll)

        for ll in filter(lambda ll: ll.leave_id.category_type == 'NO_PAY', leave_lines_ids):
            suspension_days[ll.leave_id].append(ll)

        holiday_book_lines = []
        for leave_id, lines in holidays.items():
            leave_days = len(lines)
            non_working_days = len([
                ll for ll in lines
                if payslip_id.contract_id.is_rest_day(ll.date) or self.env['hr.days.off.year'].is_day_off(ll.date)
            ])
            days_31 = 0
            if not leave_id.leave_type_id.apply_day_31:
                days_31 = self._get_days_31(
                    payslip_id.contract_id, leave_id.date_start, leave_id.date_end)
            days_enjoyed = (leave_days + days_31) - non_working_days

            holiday_book_lines.append({
                'contract_id': payslip_id.contract_id.id,
                'leave_id': leave_id.id,
                'payslip_id': payslip_id.id,
                'days_enjoyed': days_enjoyed,
            })

        for leave_id, lines in money_holidays.items():
            leave_days = len(lines)
            holiday_book_lines.append({
                'contract_id': payslip_id.contract_id.id,
                'leave_id': leave_id.id,
                'payslip_id': payslip_id.id,
                'days_paid': leave_days,
            })

        for leave_id, lines in suspension_days.items():
            leave_days = len(lines)
            holiday_book_lines.append({
                'contract_id': payslip_id.contract_id.id,
                'leave_id': leave_id.id,
                'payslip_id': payslip_id.id,
                'days_suspension': leave_days,
            })

        self.env['hr.holiday.book'].create(holiday_book_lines)

    def get_days_leave(self, date_start, date_to):
        leave_lines_ids = self.env['hr.leave.line'].search([
            ('payslip_id', '!=', False),
            ('payslip_id.state', '=', 'paid'),
            ('payslip_id.contract_id.state', '=', 'open'),
            ('leave_id.contract_id', '=', self.id),
            ('leave_id.leave_type_id.category_type', '!=', 'VAC_MONEY'),
            ('date', '>=', date_start),
            ('date', '<=', date_to)
        ])
        return leave_lines_ids

    def remove_to_holiday_book(self, payslip_id):
        self.env['hr.holiday.book'].search([
            ('payslip_id', '=', payslip_id.id)
        ]).unlink()

    def _get_format_vat(self):
        return "{:,.0f}".format(int(self.employee_id.identification_id)).replace(",", ".")

    def _get_date_start(self):
        return self.date_start.strftime("%d/%m/%Y")

    def _get_date_end(self):
        if self.settlement_date:
            return self.settlement_date.strftime("%d/%m/%Y")
        return ''

    def _get_current_date(self):
        return date.today().strftime("%d/%m/%Y")
    
    
    ##############################
    ###HOLIDAY BOOK PER PERIOD####
    ##############################

    def _calculate_holiday_book_period(self):
        """Recalcula el libro de vacaciones por período anual del contrato.

        Genera una línea por cada período anual del contrato. Si un período tiene
        vacaciones (VAC o VAC_MONEY) registradas en holiday_book_ids, se crea una
        línea adicional por cada ausencia. El saldo inicial (initial_balance) se
        prorratea en los primeros períodos.
        """
        self.holiday_book_period_ids.unlink()

        contract_start = self.date_start
        if not contract_start:
            return

        reference_date = date.today()

        # --- Generar períodos anuales ---
        periods = []
        current_start = contract_start
        while current_start <= reference_date:
            next_start = current_start + relativedelta(years=1)
            current_end = min(next_start - timedelta(days=1), reference_date)
            periods.append((current_start, current_end))
            current_start = next_start

        if not periods:
            return

        # --- Saldo inicial de holiday_book_ids ---
        initial_entries = self.holiday_book_ids.filtered(lambda hb: hb.initial_balance)
        remaining_initial_enjoyed = sum(initial_entries.mapped('days_enjoyed'))
        remaining_initial_paid = sum(initial_entries.mapped('days_paid'))
        remaining_initial_suspension = sum(initial_entries.mapped('days_suspension'))

        # --- Entradas regulares (con ausencia asociada) agrupadas por período ---
        regular_entries = self.holiday_book_ids.filtered(
            lambda hb: not hb.initial_balance and hb.leave_id
        )

        entries_by_period = defaultdict(list)
        for entry in regular_entries:
            leave_start = entry.leave_id.date_start
            if not leave_start:
                continue
            for idx, (p_start, p_end) in enumerate(periods):
                if p_start <= leave_start <= p_end:
                    entries_by_period[idx].append(entry)
                    break

        # --- Construir líneas ---
        running_pending = 0.0
        lines_to_create = []

        for idx, (period_start, period_end) in enumerate(periods):
            is_last_period = idx == len(periods) - 1

            # Días de suspensión (licencias NO_PAY)
            current_suspension_days = self.env['hr.leave.line'].get_days_not_worked(
                self, period_start, period_end, False,
                {'period': SimpleNamespace(start=period_start, end=period_end)},
                False
            )

            total_days = days360(period_start, period_end)

            # Suspensiones de saldo inicial a distribuir en este período
            initial_suspension_this_period = 0
            if remaining_initial_suspension > 0:
                available_suspension_days = max(total_days - current_suspension_days, 0)
                if is_last_period:
                    initial_suspension_this_period = remaining_initial_suspension
                else:
                    initial_suspension_this_period = min(
                        remaining_initial_suspension,
                        available_suspension_days,
                    )
                remaining_initial_suspension -= initial_suspension_this_period

            suspension_days = current_suspension_days + initial_suspension_this_period

            # Días trabajados y causados
            days_worked = total_days - suspension_days
            days_accrued = days_worked * 15 / 360

            running_pending += days_accrued

            # Saldo inicial a distribuir en este período
            initial_enjoyed_this_period = 0
            initial_paid_this_period = 0
            available_initial_days = days_accrued
            if remaining_initial_enjoyed > 0 and available_initial_days > 0:
                initial_enjoyed_this_period = (
                    remaining_initial_enjoyed
                    if is_last_period
                    else min(remaining_initial_enjoyed, available_initial_days)
                )
                remaining_initial_enjoyed -= initial_enjoyed_this_period
                available_initial_days -= initial_enjoyed_this_period

            if remaining_initial_paid > 0 and (available_initial_days > 0 or is_last_period):
                initial_paid_this_period = (
                    remaining_initial_paid
                    if is_last_period
                    else min(remaining_initial_paid, available_initial_days)
                )
                remaining_initial_paid -= initial_paid_this_period

            # Entradas de vacaciones en este período
            period_entries = sorted(
                entries_by_period.get(idx, []),
                key=lambda e: e.leave_id.date_start
            )

            initial_consumed_this_period = initial_enjoyed_this_period + initial_paid_this_period
            has_content = (
                initial_consumed_this_period > 0
                or initial_suspension_this_period > 0
                or period_entries
            )

            if not has_content:
                # Sin vacaciones ni saldo inicial → una sola línea informativa
                lines_to_create.append({
                    'contract_id': self.id,
                    'date_from': period_start,
                    'date_to': period_end,
                    'days_worked': days_worked,
                    'days_suspension': suspension_days,
                    'days_accrued': days_accrued,
                    'days_payroll': 0,
                    'days_enjoyed': 0,
                    'days_validated': 0,
                    'days_paid': 0,
                    'days_pending': running_pending,
                })
            else:
                first_line = True

                # Línea de saldo inicial (si aplica)
                if initial_consumed_this_period > 0 or initial_suspension_this_period > 0:
                    running_pending -= initial_consumed_this_period
                    lines_to_create.append({
                        'contract_id': self.id,
                        'date_from': period_start,
                        'date_to': period_end,
                        'days_worked': days_worked,
                        'days_suspension': suspension_days,
                        'days_accrued': days_accrued,
                        'days_payroll': 0,
                        'days_enjoyed': initial_enjoyed_this_period,
                        'days_validated': initial_enjoyed_this_period,
                        'days_paid': initial_paid_this_period,
                        'days_pending': running_pending,
                    })
                    first_line = False

                # Líneas por cada ausencia de vacaciones
                for entry in period_entries:
                    leave = entry.leave_id
                    category_type = leave.leave_type_id.category_type

                    # Días en nómina = total de líneas de la ausencia
                    leave_lines_count = self.env['hr.leave.line'].search_count([
                        ('leave_id', '=', leave.id),
                        ('state', 'in', ('validated', 'paid')),
                    ])

                    if category_type == 'VAC':
                        days_enjoyed_val = entry.days_enjoyed
                        days_paid_val = 0
                    elif category_type == 'VAC_MONEY':
                        days_enjoyed_val = 0
                        days_paid_val = entry.days_paid
                    else:
                        days_enjoyed_val = 0
                        days_paid_val = 0

                    running_pending -= (days_enjoyed_val + days_paid_val)

                    lines_to_create.append({
                        'contract_id': self.id,
                        'date_from': period_start,
                        'date_to': period_end,
                        'days_worked': days_worked,
                        'days_suspension': suspension_days,
                        'days_accrued': days_accrued if first_line else 0,
                        'days_payroll': leave_lines_count,
                        'days_enjoyed': days_enjoyed_val,
                        'days_validated': days_enjoyed_val,
                        'days_paid': days_paid_val,
                        'days_pending': running_pending,
                        'date_start_vacation': leave.date_start,
                        'date_end_vacation': leave.date_end,
                        'leave_id': leave.id,
                    })
                    first_line = False

        if lines_to_create:
            self.env['hr.holiday.book.period'].create(lines_to_create)

    def download_holiday_book_report(self):
        """Genera y descarga el reporte Excel del libro de vacaciones."""
        self.update_days_left()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Libro de Vacaciones')

        # Formatos
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter',
        })
        subtitle_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'align': 'left',
        })
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#4472C4', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
        })
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        date_fmt = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'num_format': 'dd/mm/yyyy',
        })
        number_fmt = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'num_format': '#,##0.00',
        })
        pending_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter',
            'num_format': '#,##0.00', 'bg_color': '#D6E4F0',
        })

        # Encabezado del reporte
        employee_name = self.employee_id.name or ''
        company_name = self.company_id.name or ''
        doc_number = self.employee_id.identification_id or ''

        worksheet.merge_range('A1:N1', f'LIBRO DE VACACIONES - {company_name}', title_fmt)
        worksheet.write('A3', 'Empleado:', subtitle_fmt)
        worksheet.write('B3', employee_name, subtitle_fmt)
        worksheet.write('A4', 'Documento:', subtitle_fmt)
        worksheet.write('B4', doc_number, subtitle_fmt)
        worksheet.write('A5', 'Contrato:', subtitle_fmt)
        worksheet.write('B5', self.name or '', subtitle_fmt)
        worksheet.write('A6', 'Fecha inicio:', subtitle_fmt)
        worksheet.write('B6', self.date_start.strftime('%d/%m/%Y') if self.date_start else '')
        worksheet.write('D3', 'Días pendientes:', subtitle_fmt)
        worksheet.write('E3', self.days_left, number_fmt)
        worksheet.write('D4', 'Fecha reporte:', subtitle_fmt)
        worksheet.write('E4', date.today().strftime('%d/%m/%Y'))

        # Cabeceras de la tabla
        headers = [
            'Fecha Inicial', 'Fecha Final', 'Días Trabajados', 'Días Suspendidos',
            'Días Causados', 'Días en Nómina', 'Días Disfrutados', 'Días Validados',
            'Días Pagados', 'Días Pendientes', 'Inicio Vacaciones', 'Fin Vacaciones',
        ]

        row = 7
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_fmt)

        # Anchos de columna
        col_widths = [14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 16, 16]
        for i, w in enumerate(col_widths):
            worksheet.set_column(i, i, w)

        # Datos
        row = 8
        for line in self.holiday_book_period_ids:
            worksheet.write(row, 0, line.date_from.strftime('%d/%m/%Y') if line.date_from else '', date_fmt)
            worksheet.write(row, 1, line.date_to.strftime('%d/%m/%Y') if line.date_to else '', date_fmt)
            worksheet.write(row, 2, line.days_worked, number_fmt)
            worksheet.write(row, 3, line.days_suspension, number_fmt)
            worksheet.write(row, 4, line.days_accrued, number_fmt)
            worksheet.write(row, 5, line.days_payroll, number_fmt)
            worksheet.write(row, 6, line.days_enjoyed, number_fmt)
            worksheet.write(row, 7, line.days_validated, number_fmt)
            worksheet.write(row, 8, line.days_paid, number_fmt)
            worksheet.write(row, 9, line.days_pending, pending_fmt)
            worksheet.write(row, 10, line.date_start_vacation.strftime('%d/%m/%Y') if line.date_start_vacation else '', date_fmt)
            worksheet.write(row, 11, line.date_end_vacation.strftime('%d/%m/%Y') if line.date_end_vacation else '', date_fmt)
            row += 1

        workbook.close()
        output.seek(0)

        report_name = f'LIBRO_VACACIONES_{company_name}{date.today().isoformat()}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': report_name,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'hr.contract',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def _get_format_salary(self):
        format_value = "{:,.2f}".format(self.wage).replace(
            ",", "X").replace(".", ",").replace("X", ".")
        return f"${format_value}"

    def _get_format_company_vat(self):
        company_vat = "{:,.0f}".format(
            int(self.company_id.partner_id.vat)).replace(",", ".")
        company_vat += "-" + self.company_id.partner_id.l10n_co_verification_code
        return company_vat

    def _get_variable_salary(self):
        current_date = date.today()
        data = {}
        last_day = current_date.replace(day=1) - timedelta(days=1)
        month = (last_day.month - 2) % 12 or 12
        year = last_day.year - (1 if month > last_day.month else 0)
        first_day = date(year, month, 1)

        if first_day < self.date_start:
            first_day = self.date_start
        if self.settlement_date and last_day > self.settlement_date:
            last_day = self.settlement_date

        worked_days = days360(first_day, last_day)

        period = {
            'start': first_day,
            'end': last_day
        }

        categories = ('earnings', 'comp_earnings', 'o_salarial_earnings')

        self.env['hr.concept']._get_total_concept_categories(
            self._cr, data, period, self.id, exclude=('BASICO',), categories=categories)

        previous_variable = sum(data.values())

        variable_salary = (previous_variable / worked_days) * 30

        format_value = "{:,.2f}".format(variable_salary).replace(
            ",", "X").replace(".", ",").replace("X", ".")

        return f"${format_value}"

    def _get_days_31(self, contract, date_from, date_to):
        count_days = 0
        while date_from <= date_to:
            if date_from.day == 31:
                if contract.is_rest_day(date_from) or self.env['hr.days.off.year'].is_day_off(date_from):
                    date_from += timedelta(days=1)
                    continue
                count_days += 1
            date_from += timedelta(days=1)
        return count_days

    def _set_worked_days(self, date_from_wz, date_from, date_to):
        for record in self:
            date_start_ref = date_from
            date_to_ref = date_to
            if record.settlement_date and record.settlement_date < date_start_ref:
                worked_days = 0
            else:
                if record.date_start > date_start_ref:
                    date_start_ref = record.date_start
                if record.settlement_date and record.settlement_date < date_to_ref:
                    date_to_ref = record.settlement_date
                if date_start_ref < date_from_wz:
                    date_start_ref = date_from_wz
                worked_days = days360(date_start_ref, date_to_ref)
                days_suspension = 0
                for holiday_book in record.holiday_book_ids:
                    days_suspension += holiday_book.days_suspension
                worked_days -= days_suspension
                if worked_days + days_suspension < 30:
                    worked_days = 30
            self._cr.execute('UPDATE hr_contract SET worked_days = {days} WHERE id = {id}'.format(
                days=worked_days, id=record.id))

    @api.model
    def recreate_book_lines(self):
        leave_lines_ids = self.env['hr.leave.line'].search([
            ('payslip_id', '!=', False),
            ('payslip_id.state', '=', 'paid'),
            ('payslip_id.contract_id.state', '=', 'open')
        ])
        payslip_ids = [x.payslip_id.id for x in leave_lines_ids]
        payslips = self.env['hr.payslip'].search([('id', 'in', payslip_ids)])
        for payslip in payslips:
            self.remove_to_holiday_book(payslip)
            self.add_to_holiday_book(payslip)

    @api.model
    def update_massive_days_contract(self):
        contracts = self.env['hr.contract'].search([('state', '=', 'open')])
        for contract in contracts:
            contract.update_days_left()

    def _get_worked_days(self):
        return days360(self.date_start, self.settlement_date)

    @api.model
    def default_get(self, field_list):
        res = super().default_get(field_list)
        res['location_code'] = self.env.company.chart_template
        return res
