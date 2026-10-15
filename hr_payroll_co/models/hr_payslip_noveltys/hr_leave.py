# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from odoo.addons.utilities_collection.time import days360
from calendar import monthrange


class HrLeave(models.Model):
    _name = 'hr.leave'
    _inherit = 'model.basic.payslip.novelty'
    _description = 'Ausencia'
    _order = 'name'

    leave_type_id = fields.Many2one(
        comodel_name='hr.leave.type', string='Categoría de Ausencia', required=True)
    leave_line_ids = fields.One2many(
        comodel_name='hr.leave.line', inverse_name='leave_id', readonly=True, string='Lineas de Ausencia')
    date_end = fields.Date(string='Fecha Final', required=True)
    amount = fields.Float(string='Valor', readonly=True,
                          compute='_compute_amount', store=True)
    category_type = fields.Selection(
        string='Tipo',
        readonly=True, related='leave_type_id.category_type')
    days_vac_money = fields.Integer(string='Cantidad de días')
    number_order_eps = fields.Char(string='Número autorización')
    is_extension = fields.Boolean(string='Es prórroga', default=False)
    extension_id = fields.Many2one(comodel_name='hr.leave', string='Prórroga')
    sequence_start = fields.Integer(string="Inicio de secuencia", default=1)
    segment_by_holdidays = fields.Boolean(
        string='Segmentar en con días no habiles', default=False)
    holidays_leave_type_id = fields.Many2one(
        comodel_name='hr.leave.type', string='Categoría de Ausencia días no habiles')
    code_cie10_id = fields.Many2one(
        comodel_name='hr.leave.code.cie10.table', string='Código CIE10')
    diagnosis_description = fields.Text(
        string='Descripción del Diagnóstico', compute='_compute_diagnosis_description', store=True)
    actual_start_date = fields.Date(string='Fecha Real de Inicio')
    actual_end_date = fields.Date(string='Fecha Real de Fin')
    apply_manual_ibc = fields.Boolean(string='Aplicar IBC manual', default=False)
    manual_ibc = fields.Float(string='IBC Manual')
    amount_adjusted_to_smmlv = fields.Boolean(
        string='Monto ajustado al SMMLV (día)',
        default=False,
        help='Indica si al menos un día de la incapacidad se liquidó aplicando el piso del salario '
             'mínimo legal diario (IBC previo por debajo del mínimo). Si está activo, no aplica '
             'complemento empresarial en nómina.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'seq.hr.leave') or ''
        return super(HrLeave, self).create(vals_list)

    @api.depends('leave_line_ids')
    def _compute_amount(self):
        for record in self:
            record.amount = sum([x.amount for x in record.leave_line_ids])

    @api.onchange('contract_id', 'leave_type_id')
    def _onchange_contract_id_leave_type_id(self):
        segment_by_holdidays = False
        holidays_leave_type_id = False
        if self.leave_type_id.category_type == 'VAC':
            segment_by_holdidays = True
            holidays_leave_type_id = self.env['hr.leave.type'].search([
                ('is_holiday_leave', '=', True),
                ('category_type', '=', 'VAC')
            ], limit=1).id
        res = {
            'value': {
                'is_extension': False,
                'extension_id': False,
                'segment_by_holdidays': segment_by_holdidays,
                'holidays_leave_type_id': holidays_leave_type_id
            },
        }
        return res

    @api.onchange('is_extension')
    def _onchange_is_extension(self):
        if not self.is_extension:
            res = {
                'value': {
                    'extension_id': False,
                },
            }
            return res

    @api.depends('code_cie10_id')
    def _compute_diagnosis_description(self):
        for record in self:
            if record.code_cie10_id:
                record.diagnosis_description = record.code_cie10_id.name

    def to_confirm(self):
        for record in self:
            if record.apply_manual_ibc and record.manual_ibc <= 0:
                raise ValidationError('El IBC manual debe ser mayor a 0')
        return super().to_confirm()

    def to_validated(self):
        period = self.env['hr.period']
        for record in self:
            if record.state != 'confirm':
                continue

            if record.leave_line_ids:
                record.leave_line_ids.unlink()

            if record.category_type == 'VAC_MONEY':
                record.date_end = record.date_start + \
                    timedelta(days=record.days_vac_money - 1)
            else:
                overlap = self.env['hr.leave.line'].search(
                    [('date', '>=', record.date_start), ('date', '<=', record.date_end),
                     ('contract_id', '=', record.contract_id.id)])
                if [x for x in overlap if x.leave_id.category_type != 'VAC_MONEY']:
                    raise ValidationError(
                        'Las ausencias no permiten sobrelapamiento.')
            if not record.date_start:
                raise ValidationError('Se debe definir la fecha de inicio.')
            if not record.date_end:
                raise ValidationError('Se debe definir la fecha de fin.')
            if record.date_end < record.date_start:
                raise ValidationError(
                    'La fecha de fin debe ser mayor o igual a la fecha de inicio.')
            periods = period.get_period(
                record.date_start, record.date_end, record.contract_id.schedule_pay)
            leave_lines_cmds = record._prepare_leave_line(periods)
            # Un write explícito con leave_line_ids y amount_adjusted_to_smmlv asegura que la marca
            # (asignada dentro de _prepare_leave_line / SicknessCalculator) persista en BD en la misma
            # operación; asignar solo leave_line_ids podría no volcar otros campos sucios según el flush.
            record.write({
                'leave_line_ids': leave_lines_cmds,
                'amount_adjusted_to_smmlv': record.amount_adjusted_to_smmlv,
            })
        return super(HrLeave, self).to_validated()

    def to_paid(self):
        for record in self:
            if all([l.state == 'paid' for l in record.leave_line_ids]):
                record.state = 'paid'

    def to_draft(self):
        for record in self.filtered(lambda r: r.state == 'validated'):
            if any([l.state == 'paid' for l in record.leave_line_ids]):
                raise ValidationError(
                    'No se pueden pasar a borrador ausencias con líneas en estado Pagado.')
        for record in self.filtered(lambda r: r.state == 'validated'):
            record.leave_line_ids.unlink()
            record.amount_adjusted_to_smmlv = False
        return super(HrLeave, self).to_draft()

    def to_cancel(self):
        for record in self.filtered(lambda r: r.state == 'validated'):
            if any([l.state == 'paid' for l in record.leave_line_ids]):
                raise ValidationError(
                    'No se pueden cancelar ausencias con líneas en estado Pagado.')
        for record in self.filtered(lambda r: r.state == 'validated'):
            record.leave_line_ids.unlink()
            record.amount_adjusted_to_smmlv = False
        return super(HrLeave, self).to_cancel()

    def _prepare_leave_line(self, periods):
        self.amount_adjusted_to_smmlv = False
        if not self.category_type:
            raise ValidationError('La categoría de la ausencia no tiene tipo')

        if not periods:
            raise ValidationError(
                f'No hay períodos en estas fechas {self.date_start} y {self.date_end}')

        calculator_selector = {
            "SICKNESS": SicknessCalculator,
            "MAT_LIC": ParentalCalculator,
            "PAT_LIC": ParentalCalculator,
            "AT_EP": AtEpCalculator,
            "NO_PAY": NoPayCalculator,
            "PAY": PayCalculator,
            "VAC": VacCalculator,
            "VAC_MONEY": VacMoneyCalculator
        }

        calculator_builder = calculator_selector.get(self.category_type)
        if not calculator_builder:
            raise ValidationError(
                f'Tipo de ausencia desconocido = {self.category_type}')

        sequence, date_origin = self.get_sequence_and_date_origin()
        calculator = calculator_builder(
            date_origin,
            self.env['economic.variable'].get_value_by_date(
                'SMMLV', self.date_start),
            (bool)(self.env['ir.config_parameter'].sudo().get_param(
                'hr_payroll_co.pays_eg_b2_with_wage')),
            (bool)(self.env['ir.config_parameter'].sudo().get_param(
                'hr_payroll_co.pays_atep_b1_with_wage')),
            self.leave_type_id.holiday_payment_strategy,
            self.contract_id,
            self.env['hr.days.off.year'],
            self.leave_type_id,
            self.env['hr.concept'],
            self._cr,
            self.days_vac_money,
            leave_id=self
        )

        new_leave_line = []
        date_tmp = self.date_start
        last_year = date_tmp.year
        base_amount = calculator.get_base_amount()
        while date_tmp <= self.date_end:
            if date_tmp.year != last_year:
                calculator = calculator_builder(
                    date_tmp,
                    self.env['economic.variable'].get_value_by_date(
                        'SMMLV', date_tmp),
                    (bool)(self.env['ir.config_parameter'].sudo().get_param(
                        'hr_payroll_co.pays_eg_b2_with_wage')),
                    (bool)(self.env['ir.config_parameter'].sudo().get_param(
                        'hr_payroll_co.pays_atep_b1_with_wage')),
                    self.leave_type_id.holiday_payment_strategy,
                    self.contract_id,
                    self.env['hr.days.off.year'],
                    self.leave_type_id,
                    self.env['hr.concept'],
                    self._cr,
                    self.days_vac_money,
                    leave_id=self
                )
                base_amount = calculator.get_base_amount()
                last_year = date_tmp.year
            leave_day = calculator.get_leave_day(
                periods, date_tmp, sequence, base_amount)
            if leave_day:
                if self.segment_by_holdidays:
                    leave_day['is_rest_or_dayoff'] = self.env['hr.leave.line'].is_rest_or_daysoff(
                        self.contract_id, date_tmp)
                new_leave_line.append((0, 0, leave_day))

                if date_tmp == self.date_end:
                    self.check_deduction_days(
                        new_leave_line, date_tmp, sequence, leave_day['amount'])

            sequence += 1
            date_tmp += timedelta(days=1)

        return new_leave_line

    def get_sequence_and_date_origin(self):
        apply_extension = self.category_type in ['SICKNESS', 'AT_EP']
        if not (apply_extension and self.extension_id):
            return self.sequence_start, self.date_start

        date_origin = self.date_start
        blacklist = {self.id}
        extension_id = self.extension_id
        while extension_id:
            if extension_id.id in blacklist:
                raise ValidationError(
                    f'Error de prórroga de si misma, validar ancestros de ausencia {self.name}')
            blacklist.add(extension_id.id)
            date_origin = extension_id.date_start
            extension_id = extension_id.extension_id

        max_sequence = max(
            (x.sequence for x in self.extension_id.leave_line_ids), default=0)
        return max_sequence + 1, date_origin

    def check_deduction_days(self, new_leave_line, date_ref, sequence, amount_real):
        type_id = self.leave_type_id
        if not (type_id.category_type == 'NO_PAY' and type_id.discount_rest_day):
            return

        hr_period = self.env['hr.period']

        for i in range(7):
            date_ref += timedelta(days=1)
            if self.contract_id.is_rest_day(date_ref):
                period = hr_period.get_period(
                    date_ref, False, self.contract_id.schedule_pay)
                if not period:
                    raise ValidationError(
                        f'No se encontró periodo para esta fecha {date_ref}')
                new_leave_line.append((0, 0, {
                    'sequence': sequence,
                    'date': date_ref,
                    'period_id': period.id,
                    'state': 'validated',
                    'amount': amount_real,
                }))
                sequence += 1


class HrLeaveCalculator(ABC):

    def __init__(self, date_start, smmlv, pays_eg_b2_with_wage, pays_atep_b1_with_wage, holiday_payment_strategy,
                 contract_id, day_off_manager, type_id, concepts_manager, cr, days_vac_money, leave_id=False):
        self.date_start = date_start
        self.smmlv = smmlv
        self.pays_eg_b2_with_wage = pays_eg_b2_with_wage
        self.pays_atep_b1_with_wage = pays_atep_b1_with_wage
        self.holiday_payment_strategy = holiday_payment_strategy
        self.contract_id = contract_id
        self.day_off_manager = day_off_manager
        self.wage = contract_id.get_wage(date_start)['wage']
        self.type_id = type_id
        self.concepts_manager = concepts_manager
        self.cr = cr
        self.days_vac_money = days_vac_money
        self.leave_id = leave_id

    @abstractmethod
    def get_base_amount(self):
        pass

    def get_ibc_previous(self):
        if self.leave_id and self.leave_id.apply_manual_ibc:
            return self.leave_id.manual_ibc / 30
        return self.contract_id.get_ibc_previous(self.date_start, self.smmlv) / 30

    def get_daily_average_last_year(self, categories):
        date_to = self.date_start - relativedelta(months=1)
        date_to = date_to.replace(
            day=monthrange(date_to.year, date_to.month)[1])
        date_from = self.date_start.replace(day=1) - relativedelta(years=1)
        if self.contract_id.date_start > date_from:
            date_from = self.contract_id.date_start
        period = {'start': date_from, 'end': date_to}

        data = {}
        exclude = ('BASICO',)
        self.concepts_manager._get_total_concept_categories(
            self.cr, data, period, self.contract_id.id, exclude=exclude)

        retroactive_amount = 0.0

        days = days360(date_from, date_to)
        if self.type_id.category_type == 'VAC' and self.holiday_payment_strategy == 'with_all_avg':
            average = 0
            variable = 0
            for category in categories:
                average += data.get(category, 0) * \
                    (1 if days < 30 else 30/days)
                variable += data.get(category, 0) * \
                    (1 if days < 30 else 30/days)

            if retroactive_amount:
                average -= retroactive_amount * (1 if days < 30 else 30/days)
                variable -= data.get(category, 0) * \
                    (1 if days < 30 else 30/days)

            if variable:
                salary = 0
                months_salaries = self.contract_id.average_wage_history_by_days(
                    date_from, date_to)
                if months_salaries:
                    for months in months_salaries.values():
                        salary += sum(months.values())
                average += salary * (1 if days < 30 else 30/days)
            else:
                average += self.wage
        else:
            average = self.wage
            for category in categories:
                average += data.get(category, 0) * \
                    (1 if days < 30 else 30/days)

            if retroactive_amount:
                average -= retroactive_amount * (1 if days < 30 else 30/days)
        return average / 30

    def get_leave_day(self, periods, date, sequence, base_amount):
        if self.eval_day_31_rule() and not self.type_id.apply_day_31 and date.day == 31:
            return None

        period = None
        for p in periods:
            if p.start <= date <= p.end:
                if period is not None:
                    raise ValidationError(
                        f'Se encontraron múltiples períodos para este día {date}')
                period = p

        if period is None:
            raise ValidationError(
                f'No se encontró un período para el día {date}')

        day_amount = self.get_day_amount(base_amount, date, sequence)

        return {
            'sequence': sequence,
            'date': date,
            'period_id': period.id,
            'state': 'validated',
            'amount': day_amount,
        }

    def eval_day_31_rule(self):
        return True

    @abstractmethod
    def get_day_amount(self, base_amount, date, sequence):
        pass


class SicknessCalculator(HrLeaveCalculator):

    def get_base_amount(self):
        return self.get_ibc_previous()

    def get_day_amount(self, base_amount, date, sequence):
        rate, _, no_smmlv_limit = self.type_id.get_rate_concept_id(sequence)
        rate = rate / 100
        use_wage = self.pays_eg_b2_with_wage and sequence <= 2
        day_amount = ((self.wage / 30) if use_wage else base_amount) * rate
        minimum_amount = self.smmlv / 30 * (rate if no_smmlv_limit else 1)
        if day_amount < minimum_amount and self.leave_id:
            self.leave_id.amount_adjusted_to_smmlv = True

        return minimum_amount if day_amount < minimum_amount else day_amount


class ParentalCalculator(HrLeaveCalculator):

    def get_base_amount(self):
        return self.get_daily_average_last_year(['earnings', 'comp_earnings'])

    def get_day_amount(self, base_amount, date, sequence):
        if self.leave_id and self.leave_id.apply_manual_ibc:
            return self.leave_id.manual_ibc / 30
        day_amount = base_amount
        minimum_amount = self.smmlv / 30

        return minimum_amount if day_amount < minimum_amount else day_amount


class AtEpCalculator(HrLeaveCalculator):

    def get_base_amount(self):
        return self.get_ibc_previous()

    def get_day_amount(self, base_amount, date, sequence):
        use_wage = self.pays_atep_b1_with_wage and sequence == 1
        day_amount = (self.wage / 30) if use_wage else base_amount
        minimum_amount = self.smmlv / 30

        return minimum_amount if day_amount < minimum_amount else day_amount


class NoPayCalculator(HrLeaveCalculator):

    def get_base_amount(self):
        return 0

    def get_day_amount(self, base_amount, date, sequence):
        return base_amount


class PayCalculator(HrLeaveCalculator):

    def get_base_amount(self):
        return self.wage / 30

    def get_day_amount(self, base_amount, date, sequence):
        return base_amount


class VacCalculator(HrLeaveCalculator):

    def get_base_amount(self):
        return self.get_daily_average_last_year(['earnings', 'o_salarial_earnings'])

    def get_day_amount(self, base_amount, date, sequence):
        if self.leave_id and self.leave_id.apply_manual_ibc:
            return self.leave_id.manual_ibc / 30
        if not self.holiday_payment_strategy:
            raise ValidationError(
                'Configure el método de pago en la categoría de ausencia')

        if self.holiday_payment_strategy in ('with_avg', 'with_all_avg'):
            return base_amount
        elif self.holiday_payment_strategy == 'with_wage':
            return self.wage / 30
        elif self.holiday_payment_strategy == 'with_mixed':
            workday = self.contract_id.is_rest_day(
                date) or self.day_off_manager.is_day_off(date)
            day_amount = (self.wage / 30) if workday else base_amount

            return day_amount
        else:
            raise ValidationError(
                f'El método de pago {self.holiday_payment_strategy} no es valido')


class VacMoneyCalculator(HrLeaveCalculator):

    def get_base_amount(self):
        if self.days_vac_money <= 0:
            raise ValidationError(
                f'La cantidad de días {self.days_vac_money}, debe ser mayor a 0')

        return self.get_daily_average_last_year(['earnings', 'o_salarial_earnings', 'comp_earnings'])

    # TODO: Aca se debe calcular el base_amount * self.days_vac_money
    def get_day_amount(self, base_amount, date, sequence):
        if self.leave_id and self.leave_id.apply_manual_ibc:
            return (self.leave_id.manual_ibc / 30)
        return base_amount

    def eval_day_31_rule(self):
        return False
