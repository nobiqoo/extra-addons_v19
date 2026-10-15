# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.utilities_collection import orm
from odoo.addons.utilities_collection.time import days360
from dateutil.relativedelta import relativedelta
import base64
import csv
import io

############################################################################
# ------------------- SOLO SE SOPORTAN ValidationError --------------------#
############################################################################

CONCEPTS = [
    'BASICO', 'SUB_TRANS',
    'PRIMA_CONV', 'PRIMA_LIQ_CONV', 'PRIMA_VAC_CONV', 'PRIMA_VAC_LIQ_CONV',
    'IBD',  'DED_PENS', 'DED_EPS', 'DED_PENS_PUBLIC', 'DED_PENS_ACCAI',
    'FOND_SOL', 'FOND_SUB',
    'CES_LIQ', 'ICES_LIQ', 'CES_PART', 'ICES_PART', 'CESLY', 'ICESLY',
    'VAC_LIQ', 'PRIMA', 'BRTF', 'RTEFTE', 'PRV_BRTF_25P', 'BRTF_PRIMA', 'PRV_BRTF_40P', 'PRIMA_LIQ', 'RTF_PRIMA',
    'CES', 'ICES',
    'INDEM', 'RTF_INDEM',
    'PRV_CES', 'PRV_ICES', 'PRV_PRIMA', 'PRV_VAC',
    'PROV_PRIMA_VAC_CONV', 'PROV_PRIMA_VAC_LIQ_CONV',
    'PROV_PRIMA_NAV', 'PROV_DIA_31', 'PROV_AUX_VAC', 'PROV_ANT',
    'NETO_LIQ', 'NETO', 'NETO_CES'
]
TPCT = 'total_previous_categories'
TPCP = 'total_previous_concepts'

DAYS_YEAR = 360
_logger = logging.getLogger(__name__)


class HrConcept(models.Model):
    _name = 'hr.concept'
    _inherit = 'model.basic.payslip.novelty.type'
    _description = 'Concepto de Nómina'
    _order = 'name'

    documentation = fields.Char(string='Información')
    file_old_name = fields.Char(string='Nombre del archivo')
    file_old = fields.Binary(string='Archivo')
    apply_tax_base = fields.Boolean(string='Aplica Impuesto')
    tax_id = fields.Many2one('account.tax', string='Impuesto')
    location_code = fields.Char(
        string='Código de localización', compute='_compute_location_code', store=True)
    
    @api.depends('company_id.chart_template')
    def _compute_location_code(self):
        for record in self:
            record.location_code = record.company_id.chart_template

    def get_seq_concept_category(self):
        for i, concept in enumerate(CONCEPTS):
            if concept == self.code:
                return i
        return len(CONCEPTS)

    def sync_old_lines(self):
        for record in self:
            is_first = True
            if record.file_old:
                csv_data = base64.b64decode(record.file_old)
                csv_text = io.StringIO(csv_data.decode('utf-8'))

                csv_reader = csv.reader(csv_text, delimiter=',')
                headers = next(csv_reader, None)

                count = 0
                ids = []
                for row in csv_reader:
                    rec_id = int(row[0])
                    if rec_id == 0:
                        self.reg_adm_debit = int(
                            row[1]) if row[1] != 'False' else False
                        self.reg_adm_credit = int(
                            row[2]) if row[2] != 'False' else False
                        self.int_adm_debit = int(
                            row[3]) if row[3] != 'False' else False
                        self.int_adm_credit = int(
                            row[4]) if row[4] != 'False' else False
                        self.apr_adm_debit = int(
                            row[5]) if row[5] != 'False' else False
                        self.apr_adm_credit = int(
                            row[6]) if row[6] != 'False' else False
                        self.reg_com_debit = int(
                            row[7]) if row[7] != 'False' else False
                        self.reg_com_credit = int(
                            row[8]) if row[8] != 'False' else False
                        self.int_com_debit = int(
                            row[9]) if row[9] != 'False' else False
                        self.int_com_credit = int(
                            row[10]) if row[10] != 'False' else False
                        self.apr_com_debit = int(
                            row[11]) if row[11] != 'False' else False
                        self.apr_com_credit = int(
                            row[12]) if row[12] != 'False' else False
                        self.reg_ope_debit = int(
                            row[13]) if row[13] != 'False' else False
                        self.reg_ope_credit = int(
                            row[14]) if row[14] != 'False' else False
                        self.int_ope_debit = int(
                            row[15]) if row[15] != 'False' else False
                        self.int_ope_credit = int(
                            row[16]) if row[16] != 'False' else False
                        self.apr_ope_debit = int(
                            row[17]) if row[17] != 'False' else False
                        self.apr_ope_credit = int(
                            row[18]) if row[18] != 'False' else False
                        self.reg_pro_debit = int(
                            row[19]) if row[19] != 'False' else False
                        self.reg_pro_credit = int(
                            row[20]) if row[20] != 'False' else False
                        self.int_pro_debit = int(
                            row[21]) if row[21] != 'False' else False
                        self.int_pro_credit = int(
                            row[22]) if row[22] != 'False' else False
                        self.apr_pro_debit = int(
                            row[23]) if row[23] != 'False' else False
                        self.apr_pro_credit = int(
                            row[24]) if row[24] != 'False' else False
                        self.category = row[25] if row[25] != 'False' else False
                        self.dian_concept_id = int(
                            row[26]) if row[26] != 'False' else False
                        self.partner_type = row[27] if row[27] != 'False' else False
                        self.partner_id = int(
                            row[28]) if row[28] != 'False' else False
                        continue
                    ids.append(int(row[0]))
                    count += 1
                    _logger.info(f"Fila procesada: {row}")
                if ids:
                    if len(ids) == 1:
                        ids.append(0)
                    self._cr.execute('UPDATE hr_payslip_line SET concept_id = {id} where id in {ids}'.format(
                        id=record.id, ids=tuple(ids)))
                    _logger.info(f"Cantidad sincronizada: {count}")
                return True

    def action_export_csv(self):
        file_data = io.StringIO()
        writer = csv.writer(file_data, delimiter=',',
                            quotechar='"', quoting=csv.QUOTE_MINIMAL)

        writer.writerow(['id',
                        'reg_adm_debit', 'reg_adm_credit',
                         'int_adm_debit', 'int_adm_credit',
                         'apr_adm_debit', 'apr_adm_credit',
                         'reg_com_debit', 'reg_com_credit',
                         'int_com_debit', 'int_com_credit',
                         'apr_com_debit', 'apr_com_credit',
                         'reg_ope_debit', 'reg_ope_credit',
                         'int_ope_debit', 'int_ope_credit',
                         'apr_ope_debit', 'apr_ope_credit',
                         'reg_pro_debit', 'reg_pro_credit',
                         'int_pro_debit', 'int_pro_credit',
                         'apr_pro_debit', 'apr_pro_credit',
                         'category', 'dian_concept_id',
                         'partner_type', 'partner_id',
                         'documentation'])

        datas = self.env['hr.payslip.line'].search(
            [('concept_id', '=', self.id)], order="id asc")
        writer.writerow([0,
                        self.reg_adm_debit.id, self.reg_adm_credit.id,
                        self.int_adm_debit.id, self.int_adm_credit.id,
                        self.apr_adm_debit.id, self.apr_adm_credit.id,
                        self.reg_com_debit.id, self.reg_com_credit.id,
                        self.int_com_debit.id, self.int_com_credit.id,
                        self.apr_com_debit.id, self.apr_com_credit.id,
                        self.reg_ope_debit.id, self.reg_ope_credit.id,
                        self.int_ope_debit.id, self.int_ope_credit.id,
                        self.apr_ope_debit.id, self.apr_ope_credit.id,
                        self.reg_pro_debit.id, self.reg_pro_credit.id,
                        self.int_pro_debit.id, self.int_pro_credit.id,
                        self.apr_pro_debit.id, self.apr_pro_credit.id,
                        self.category, self.dian_concept_id.id,
                        self.partner_type, self.partner_id.id,
                        self.documentation])
        for data in datas:
            writer.writerow([data.id,
                            data.concept_id.reg_adm_debit.id, data.concept_id.reg_adm_credit.id,
                            data.concept_id.int_adm_debit.id, data.concept_id.int_adm_credit.id,
                            data.concept_id.apr_adm_debit.id, data.concept_id.apr_adm_credit.id,
                            data.concept_id.reg_com_debit.id, data.concept_id.reg_com_credit.id,
                            data.concept_id.int_com_debit.id, data.concept_id.int_com_credit.id,
                            data.concept_id.apr_com_debit.id, data.concept_id.apr_com_credit.id,
                            data.concept_id.reg_ope_debit.id, data.concept_id.reg_ope_credit.id,
                            data.concept_id.int_ope_debit.id, data.concept_id.int_ope_credit.id,
                            data.concept_id.apr_ope_debit.id, data.concept_id.apr_ope_credit.id,
                            data.concept_id.reg_pro_debit.id, data.concept_id.reg_pro_credit.id,
                            data.concept_id.int_pro_debit.id, data.concept_id.int_pro_credit.id,
                            data.concept_id.apr_pro_debit.id, data.concept_id.apr_pro_credit.id,
                            data.concept_id.category, data.concept_id.dian_concept_id.id,
                            data.concept_id.partner_type, data.concept_id.partner_id.id,
                            data.concept_id.documentation])

        file_data.seek(0)
        file_content = file_data.getvalue().encode('utf-8')
        file_data.close()

        attachment = self.env['ir.attachment'].create({
            'name': self.name + '.csv',
            'type': 'binary',
            'datas': base64.b64encode(file_content),
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    def _initialize_logs(self, data_payslip):
        logs = {
            'concept_id': self.id,
            'period_id': data_payslip['period'].id,
            'payslip_id': data_payslip['payslip_id'],
            'employee_id': data_payslip['contract'].employee_id.id,
            'contract_id': data_payslip['contract'].id,
            'company_id': self.company_id.id
        }
        if data_payslip.get('payslip_processing_id'):
            logs['payslip_processing_id'] = data_payslip.get(
                'payslip_processing_id')
        return logs

    def _compute_ibd(self, data_payslip):
        salary = 0
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        for category in ['earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']:
            salary += data_payslip.get(TPCT, {}).get(category, 0)
            salary += data_payslip.get(category, 0)

        # Descontar dinero de vacaciones monetizadas
        period = {
            'start': data_payslip['period'].start.replace(day=1),
            'end': data_payslip['period'].end,
        }
        vac_money_amount = sum(self.env['hr.leave.line'].search([
            ('contract_id', '=', data_payslip['contract'].id),
            ('state', 'in', ('validated', 'paid')),
            ('leave_id.category_type', '=', 'VAC_MONEY'),
            ('payslip_id.period_id.end', '>=', period['start']),
            ('payslip_id.period_id.start', '<=', period['end']),
        ]).mapped('amount'))
        salary -= vac_money_amount

        # Descontar vacaciones liquidadas pagadas en el mismo periodo
        data_total_vac_liq = {}
        self._get_total_concepts(
            data_payslip['cr'], data_total_vac_liq, period, data_payslip['contract'].id, ('VAC_LIQ',))

        vac_liq_amount = sum(data_total_vac_liq.values())
        salary -= vac_liq_amount

        if data_payslip['politics'][
                'hr_payroll_co.deductions_with_previous_ibc'] and data_payslip['contract'].date_start < data_payslip['period'].start.replace(day=1):
            query = '''
                SELECT
                    COALESCE(sum(HLL.amount), 0), COALESCE(count(*), 0), HL.date_start
                FROM hr_leave_line AS HLL
                INNER JOIN hr_leave AS HL
                    ON HL.id = HLL.leave_id
                INNER JOIN hr_leave_type AS HLT
                    ON HLT.id = HL.leave_type_id
                INNER JOIN hr_payslip AS HP
                    ON HP.id = HLL.payslip_id
                INNER JOIN hr_period AS PP
                    ON PP.id = HP.period_id
                WHERE
                    HL.contract_id = %(contract_id)s AND
                    PP.end >= %(start)s AND
                    PP.start <= %(end)s AND
                    HLL.state IN ('validated', 'paid') AND
                    HLT.category_type = 'VAC'
                GROUP BY HL.date_start
            '''
            param = {
                'contract_id': data_payslip['contract'].id,
                'start': period['start'],
                'end': period['end'],
            }
            apply_ibd_ded = data_payslip['politics']['hr_payroll_co.does_not_allow_ibd_less_than_smmlv']
            for amount, days, date_start in orm._fetchall(self._cr, query, param):
                if not days:
                    continue
                if apply_ibd_ded:
                    ibc_previous = data_payslip['contract'].get_ibc_previous(
                        date_start, smmlv, True)
                    data_payslip.setdefault('IBD_DED', salary)
                    data_payslip['IBD_DED'] += ibc_previous / 30 * days - amount
                ibc_previous = data_payslip['contract'].get_ibc_previous(
                    date_start, smmlv)
                salary -= amount
                salary += ibc_previous / 30 * days

        o_earnings = data_payslip.get(TPCT, {}).get('o_earnings', 0)
        o_earnings += data_payslip.get('o_earnings', 0)
        top40 = (salary + o_earnings) * 0.4
        if o_earnings > top40:
            data_payslip['IBD'] = salary + o_earnings - top40
        else:
            data_payslip['IBD'] = salary

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            data_payslip['IBD'] *= 0.7

        if data_payslip['IBD'] > 25 * smmlv:
            data_payslip['IBD'] = 25 * smmlv

    def _compute_indem(self, data_payslip, audit=False, log={}):
        settlement_type = data_payslip['contract'].settlement_type
        if not settlement_type:
            raise ValidationError('El contrato no tiene tipo de finalización.')
        elif settlement_type not in ['n_causa', 'unil']:
            return
        term = data_payslip['contract'].term
        settlement_date = data_payslip['contract'].settlement_date
        if not settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        if 'last_year' not in data_payslip:
            self.get_last_year(data_payslip, settlement_date)
        if term in ['fijo', 'obra-labor']:
            date_end = data_payslip['contract'].date_end
            if not date_end:
                raise ValidationError('El contrato no tiene fecha de fin.')
            if settlement_date > date_end:
                raise ValidationError(
                    'La fecha de liquidación debe ser menor o igual a la fecha de fin.')
            days_not_pay = days360(settlement_date, date_end) - 1
            if days_not_pay <= 0:
                return
            value, qty = data_payslip['last_year']['average'], days_not_pay
            if term == 'obra-labor' and qty < 15:
                qty = 15
            if audit:
                log['no_pay_leave_days'] = days_not_pay
        else:
            date_start = data_payslip['contract'].date_start
            if not date_start:
                raise ValidationError('El contrato no tiene fecha de inicio.')
            duration = days360(date_start, settlement_date)
            value = data_payslip['last_year']['average']
            smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
            qty, days = [30, 20] if value < 10 * smmlv / 30 else [20, 15]
            qty += (duration - 360)*days/360 if duration > 361 else 0
            if audit:
                log['contract_duration'] = duration
        data_payslip['INDEM_value'] = value
        data_payslip['INDEM_qty'] = qty
        if audit:
            log['date_from'] = str(data_payslip['contract'].date_start)
            log['date_to'] = str(settlement_date)
            log['total_base'] = data_payslip['INDEM_value']
            log['total'] = data_payslip['INDEM_value'] * \
                data_payslip['INDEM_qty']

    def _compute_social_benefits(self, data_payslip, date_from, date_to, audit=False, log={}):
        ces = ['CESLY', 'ICESLY', 'CES', 'ICES', 'CES_PART', 'CON_CES', 'PRV_CES',
               'ICES_PART', 'CES_LIQ', 'ICES_LIQ', 'PRV_CES', 'PRV_ICES']
        prv = ['PRV_CES', 'PRV_PRIMA']
        prima = ['PRIMA_LIQ', 'PRIMA', 'PRV_PRIMA']
        is_prim = self.code in prima
        is_ces = self.code in ces
        is_prv = self.code in prv
        ignore_rest_days = data_payslip['politics']['hr_payroll_co.discount_all_leave_in_social_benefits']
        is_cesly = self.code in ['CESLY']
        if is_ces:
            date_3_months_before = (
                date_to - relativedelta(months=2)).replace(day=2)
            if date_from > date_3_months_before:
                date_3_months_before = date_from + relativedelta(days=1)
            has_change_salary = data_payslip['contract'].has_change_salary(
                date_3_months_before, date_to)
            compute_average = True if has_change_salary else False
        elif is_prim:
            date_6_months_before = date_to - relativedelta(months=6)
            if date_from > date_6_months_before:
                date_6_months_before = date_from + relativedelta(days=1)
            has_change_salary = data_payslip['contract'].has_change_salary(
                date_6_months_before, date_to)
            compute_average = True if has_change_salary else False
        else:
            compute_average = True

        data_base = {}
        days_worked = days360(date_from, date_to)
        data = {
            'contract': data_payslip['contract'].id,
            'start': date_from,
            'end': date_to,
        }
        if audit:
            log['date_from'] = str(date_from)
            log['date_to'] = str(date_to)

        if days_worked < 30:
            compute_average = False

        leave_line = self.env['hr.leave.line']
        no_pay_dates = []
        if data_payslip['politics']['hr_payroll_co.discount_suspensions'] or (is_ces and not data_payslip['politics']['hr_payroll_co.apply_no_pay_leave_ces']):
            date_from_range = date_from
            if self.code == 'PRV_CES':
                if date_from.month == 1 and data_payslip['period']['start'].month != 1:
                    date_from_range = (
                        date_from + relativedelta(months=1)).replace(day=1)

            if data_payslip['period']['start'].month == 1 and self.code in ['CES', 'ICES', 'ICESLY']:
                is_cesly = True
            data['type'] = ('NO_PAY',)
            # Mismas fechas que se descuentan de days_worked, para descontarlas también
            # del salario al promediar (numerador y denominador consistentes).
            no_pay_dates = leave_line.get_no_pay_dates(
                data_payslip['contract'], date_from_range, date_to, data_payslip, is_cesly)
            days_not_worked = len(no_pay_dates)
            days_worked -= days_not_worked
            if audit:
                log['no_pay_leave_days'] = days_not_worked

        # Compute Salary
        social_benefits_with_last_wage = data_payslip['politics'][
            'hr_payroll_co.social_benefits_with_last_wage']
        if social_benefits_with_last_wage or not has_change_salary:
            full_wage = data_payslip['contract'].get_wage(date_to)
            data_base['salary'] = full_wage['wage'] * days_worked / \
                30 if days_worked > 30 else full_wage['wage']
        else:
            if self.code in ('PRIMA', 'PRIMA_LIQ', 'CES_LIQ', 'ICES', 'CES', 'PRV_CES', 'PRV_PRIMA', 'CESLY', 'ICESLY'):
                data_base['salary'] = 0
                months_salaries = data_payslip['contract'].average_wage_history_by_days(
                    date_from, date_to, date_excludes=no_pay_dates)
                if months_salaries:
                    for salary in months_salaries.values():
                        data_base['salary'] += sum(salary.values())
            else:
                data_base['salary'] = 0
                if self.code != 'CES_LIQ':
                    data['type'] = ('MAT_LIC', 'PAT_LIC')
                    license_days = leave_line.get_info_from_leave_type(
                        data_payslip['cr'], data)[1]
                    data_base['license'] = license_days
                    if audit:
                        log['paternal_license_days'] = license_days

                    data_base['salary'] += self.get_salary_in_leave(
                        data_payslip['cr'], data)

                concepts = ('BASICO',)
                data_salary = {}
                self._get_total_concepts(
                    data_payslip['cr'], data_salary, data, data['contract'], concepts)
                data_base['salary'] += sum(data_salary.values())
                data_base['salary'] += data_payslip.get('BASICO', (0,))[0]
        if audit:
            log['worked_days'] = days_worked

        # Cumpute Variable Salary
        data_variable_salary = {}
        self.get_variable_salary(
            data_payslip['cr'], data_variable_salary, data, data['contract'])
        
        if self.code in ('CESLY', 'CES', 'ICESLY', 'ICES'):
            actual_variable = 0.0
        else:
            actual_variable = self._get_actual_variable_salary(data_payslip)
        previous_variable = sum(data_variable_salary.values())
        data_base['variable'] = actual_variable + previous_variable

        if self.code in ('PRIMA', 'CES_LIQ', 'PRIMA_LIQ', 'PRV_CES', 'PRV_PRIMA', 'CESLY', 'ICESLY'):
            data_base['variable'] -= self._get_current_retroactive(
                data_payslip, date_from, date_to)

        conv_amounts = self._get_actual_conv_amount(data_payslip, data)
        if conv_amounts:
            if self.code in ('CES_LIQ', 'PRIMA_LIQ', 'PRV_ICES', 'PRV_CES', 'CESLY', 'ICESLY'):
                data_base['variable'] += conv_amounts
            else:  
                data_base['variable'] += (conv_amounts / days_worked * 30)

        # Compute Static Salary
        earnings = data_variable_salary.get('earnings', 0)
        earnings += data_base['salary']

        if days_worked <= 30:
            earnings_month = earnings
        else:
            earnings_month = earnings * 30 / days_worked

        if data_payslip['politics']['hr_payroll_co.average_sub_trans']:
            concepts = ('SUB_TRANS', 'SUB_CONNE')
            data_static_salary = {}
            self._get_total_concepts(
                data_payslip['cr'], data_static_salary, data, data['contract'], concepts)

            data_base['static'] = sum(data_static_salary.values())
            data_base['static'] += data_payslip.get('SUB_TRANS', 0)
            if 0 < days_worked < 30:
                data_base['static'] = data_base['static'] / days_worked * 30
        else:
            if not data_payslip['contract'].skip_commute_allowance:
                year_month = (date_to.year, date_to.month)

                ev_smml = data_payslip['economic_variables']['SMMLV']
                if year_month not in ev_smml:
                    ev_smml[year_month] = self.env['economic.variable'].get_value_by_date(
                        'SMMLV', date_to)
                smmlv = ev_smml[year_month]

                ev_sub_trans = data_payslip['economic_variables']['SUB_TRANS']
                if year_month not in ev_sub_trans:
                    ev_sub_trans[year_month] = self.env['economic.variable'].get_value_by_date(
                        'SUB_TRANS', date_to)
                subsidy = ev_sub_trans[year_month]

                if (is_prv and days_worked < 30) or (self.code in ('PRIMA', 'CES_LIQ', 'PRIMA_LIQ', 'CESLY', 'ICES_LIQ', 'CES', 'ICES', 'ICESLY') and days_worked < 30):
                    earnings_month_30 = earnings
                    if earnings_month_30 <= 2 * smmlv:
                        data_base['static'] = subsidy
                else:
                    earnings_month_30 = (
                        earnings_month / days_worked) * 30 if days_worked < 30 else earnings_month
                    if earnings_month_30 <= 2 * smmlv:
                        data_base['static'] = subsidy * days_worked / 30

        # Compute Base / Total
        if self.code in ('PRIMA_LIQ', 'PRIMA', 'PRV_PRIMA', 'CES', 'ICES', 'CES_LIQ', 'ICES_LIQ') and days_worked < 30 and data_payslip['politics']['hr_payroll_co.prima_avg_variable']:
            data_base['variable'] = data_base['variable'] / days_worked * 30
        base = sum(data_base.values())
        if not data_payslip['politics']['hr_payroll_co.average_prima_in_settlement_less_than_month'] and self.code in ('PRIMA_LIQ', 'CES_LIQ') and days_worked <= 30:
            base -= data_base.get('variable', 0)
            days_range = 180 if self.code == 'PRIMA_LIQ' else 360
            base_variable = (data_base.get('variable', 0) / days_range) * 30
            base_day = base / 30
            base = (base_day * 30) + base_variable
        else:
            base *= 1 if days_worked <= 30 else (30 / days_worked)
        if data_payslip['contract'].is_conventional and self.code in ('CES', 'ICES', 'CES_LIQ', 'ICES_LIQ', 'PRIMA', 'PRIMA_LIQ', 'PRV_CES', 'PRV_ICES', 'PRV_PRIMA'):
            base += data_payslip['contract'].room_prima_amount
        total = base * days_worked / \
            data_payslip['contract'].get_benefits_days_base()
        if audit:
            log['worked_days'] = days_worked
            log['total_salary'] = data_base.get("salary", 0)
            log['total_earnings'] = data_variable_salary.get("earnings", 0)
            log['total_comp_earnings'] = data_variable_salary.get(
                "comp_earnings", 0)
            log['total_o_salarial_earnings'] = data_variable_salary.get(
                "o_salarial_earnings", 0)
            log['total_variable'] = data_base.get("variable", 0)
            log['total_subsidy'] = data_base.get("static", 0)
            log['total_base'] = base
            log['total'] = total
        if self.code in ('ICES', 'ICES_LIQ', 'ICESLY') and data_payslip['politics']['hr_payroll_co.apply_no_pay_leave_intces']:
            data['type'] = ('NO_PAY',)
            days_not_worked = leave_line.get_days_not_worked(
                data_payslip['contract'], date_from_range, date_to, ignore_rest_days, data_payslip, is_cesly)
            days_worked += days_not_worked
        return base, days_worked, total

    def _compute_base_less_tham_smmlv(self, data_payslip, rate):
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        day_smmlv = smmlv / 30
        is_biweekly = data_payslip['period'].type_period == 'BIWEEKLY'
        is_q1 = is_biweekly and data_payslip['period'].type_biweekly == 'FIRST'
        date_from = data_payslip['period'].start
        date_to = data_payslip['period'].end
        if is_biweekly and not is_q1:
            date_from = date_from.replace(day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        if data_payslip['contract'].settlement_date and date_to > data_payslip['contract'].settlement_date:
            date_to = data_payslip['contract'].settlement_date
        apprentice_to_worker_date = data_payslip['contract'].apprentice_to_worker_date
        if (data_payslip['contract'].fiscal_type_id.code == '19'
                and apprentice_to_worker_date
                and date_from < apprentice_to_worker_date <= date_to):
            date_from = apprentice_to_worker_date
        query_params = {
            'contract': data_payslip['contract'].id,
            'start': date_from,
            'end': date_to,
        }
        if data_payslip['payslip_type_id'].category == 'VAC':
            worked_days = len(
                [d['day'] for d in data_payslip['payslip_days'] if d['day_type'] == 'A'])
        else:
            worked_days = days360(date_from, date_to)
        worked_days -= self.get_days_no_pay(data_payslip, query_params.copy())

        base_smmlv = day_smmlv * worked_days
        if data_payslip.get('IBD_DED', 0) > 0:
            ibd = data_payslip['IBD_DED'] if data_payslip['IBD_DED'] > data_payslip['IBD'] else data_payslip['IBD']
        else:
            ibd = data_payslip['IBD']
        ibd -= self._get_wage_in_teaching_phase(data_payslip)
        if self.code == 'DED_PENS' and data_payslip['politics']['hr_payroll_co.assumed_pen_not_remunerate_licences']:
            no_pay_days = len(self.env['hr.leave.line'].search([
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('contract_id', '=', data_payslip['contract'].id),
                ('state', 'in', ('validated', 'paid')),
                ('leave_id.category_type', '=', 'NO_PAY')
            ]))
            if no_pay_days:
                ibc_previous = data_payslip['contract'].get_ibc_previous(
                    data_payslip['period'].end, smmlv, True)
                ibd += (ibc_previous / 30) * no_pay_days
        base = ibd if ibd > base_smmlv else base_smmlv

        total = base * rate / 100
        return total, base

    def _get_rate_trtefte(self, data_payslip, value):
        uvt = data_payslip['economic_variables']['UVT'][data_payslip['current_year_month']]
        table = data_payslip['economic_variables']['TRTEFTE'][data_payslip['current_year_month']]

        base = value / uvt
        rtefte = 0
        for t in table:
            compute = False
            lower_limit = t.get('lower_limit')
            upper_limit = t.get('upper_limit')

            if lower_limit is None and upper_limit is not None and base <= upper_limit:
                compute = True
            elif None not in (lower_limit, upper_limit) and lower_limit < base <= upper_limit:
                compute = True
            elif lower_limit is not None and upper_limit is None and lower_limit < base:
                compute = True

            if compute:
                subtract = t.get('subtract', 0)
                rate = t.get('rate', 0)
                add = t.get('add', 0)
                rtefte = (base - subtract) * rate / 100 + add
                rtefte *= uvt * 100 / value
                break  # Found the correct range
        return rtefte

    def _get_total_concepts(self, cr, total_previous, period, contract, concepts):
        """
        Consulta las lineas de nomina y agrupa por categoria
        @params:
            total_previous: Diccionario donde se guardaran los datos
            period: Objeto tipo hr.period o Dicionario con {inicio,fin}
            contract: ID del contrato
            concepts: Tupla de conceptos a consultar
        @return:
            None
        """
        param = {
            'concepts': concepts,
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        query = f"""
        SELECT HC.code, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_concept as HC
            ON HC.id = HPL.concept_id
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        WHERE
            HP.state = 'paid' AND
            PP.end >= %(start)s AND
            PP.start <= %(end)s AND
            HP.contract_id = %(contract)s AND
            HC.code in %(concepts)s
        GROUP BY HC.code
        """
        data = orm._fetchall(cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = d[1]
            else:
                total_previous[d[0]] += d[1]

    def _get_ces_consignment_cutoff(self, cr, contract, period):
        # Las cesantias parciales pagadas antes de la consignacion anual del año
        # anterior ya se descontaron en esa liquidacion (concepto CES); no deben
        # volver a restarse en la liquidacion del contrato.
        param = {
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        query = """
        SELECT max(PP.end)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_concept as HC
            ON HC.id = HPL.concept_id
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        WHERE
            HP.state = 'paid' AND
            HC.code = 'CES' AND
            HP.contract_id = %(contract)s AND
            PP.start >= %(start)s AND
            PP.end <= %(end)s
        """
        data = orm._fetchall(cr, query, param)
        return data[0][0] if data and data[0][0] else None

    def _get_total_concept_categories(self, cr, total_previous, period, contract, exclude=False, categories=False):
        """
        Consulta las lineas de nomina y agrupa por categoria
        @params:
            total_previous: Diccionario donde se guardaran los datos
            period: Objeto tipo hr.period o Dicionario con {'start','end'}
            contract: ID del contrato
            exclude: Tupla con codigo de conceptos a excluir
            categories: Tupla de categorias a consultar
        @return:
            None
        """
        if not categories:
            categories = ('earnings', 'o_salarial_earnings',
                          'comp_earnings', 'o_rights', 'o_earnings')
        param = {
            'categories': categories,
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        subquery = ['', '']
        if exclude:
            subquery[0] = "LEFT JOIN hr_concept as HC ON HC.id = HPL.concept_id"
            subquery[1] = "AND (HC.code IS NULL or HC.code not in %(exclude)s)"
            param['exclude'] = exclude
        query = f"""
        SELECT HPL.category, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        {subquery[0]}
        WHERE
            HP.state = 'paid' AND
            HPL.category IN %(categories)s AND
            PP.end >= %(start)s AND
            PP.start <= %(end)s AND
            HP.contract_id = %(contract)s
            AND HPL.total IS NOT NULL
            {subquery[1]}
        GROUP BY HPL.category
        """
        data = orm._fetchall(cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = d[1]
            else:
                total_previous[d[0]] += d[1]

    def _get_total_concept_by_code(self, cr, total_previous, period, contract, codes):
        """
        Consulta las lineas de nomina y agrupa por categoria
        @params:
            total_previous: Diccionario donde se guardaran los datos
            period: Objeto tipo hr.period o Dicionario con {'start','end'}
            contract: ID del contrato
            exclude: Tupla con codigo de conceptos a excluir
            categories: Tupla de categorias a consultar
        @return:
            None
        """

        param = {
            'codes': codes,
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        query = f"""
        SELECT HPL.category, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        INNER JOIN hr_concept as HC ON HC.id = HPL.concept_id 
        WHERE
            HP.state = 'paid' AND
            PP.end >= %(start)s AND
            PP.start <= %(end)s AND
            HP.contract_id = %(contract)s
            AND HC.code in %(codes)s
        GROUP BY HPL.category
        """
        data = orm._fetchall(cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = d[1]
            else:
                total_previous[d[0]] += d[1]

    def _get_total_leave_by_code(self, cr, total_previous, period, contract, codes):
        """
        Consulta las lineas de nomina y agrupa por categoria
        @params:
            total_previous: Diccionario donde se guardaran los datos
            period: Objeto tipo hr.period o Dicionario con {'start','end'}
            contract: ID del contrato
            exclude: Tupla con codigo de conceptos a excluir
            categories: Tupla de categorias a consultar
        @return:
            None
        """

        param = {
            'codes': codes,
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        query = f"""
        SELECT HLT.category_type, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        INNER JOIN hr_leave as HL ON HL.id = HPL.leave_id
        INNER JOIN hr_leave_type as HLT ON HLT.id = HL.leave_type_id
        WHERE
            HL.state IN ('paid', 'validated') AND
            PP.end >= %(start)s AND
            PP.start <= %(end)s AND
            HP.contract_id = %(contract)s
            AND HLT.category_type in %(codes)s
        GROUP BY HLT.category_type
        """
        data = orm._fetchall(cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = d[1]
            else:
                total_previous[d[0]] += d[1]

    def _get_novelties_vst(self, cr, total_previous, period, contract):
        param = {
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        query = f"""
        SELECT HPL.category, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        INNER JOIN hr_novelty as HN 
            ON HN.id = HPL.novelty_id
        INNER JOIN hr_novelty_type as HNT
            ON HNT.id = HN.novelty_type_id
        WHERE
            HP.state = 'paid' AND
            PP.end >= %(start)s AND
            PP.start <= %(end)s AND
            HP.contract_id = %(contract)s
            AND HNT.include_like_vst_pila = 't'
        GROUP BY HPL.category
        """
        data = orm._fetchall(cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = d[1]
            else:
                total_previous[d[0]] += d[1]

    def _get_last_paid_concept(self, cr, contract, concept_code, date_from, date_to):
        param = {
            'contract': contract,
            'concept_code': concept_code,
            'date_from': date_from,
            'date_to': date_to,
        }
        query = f"""
        SELECT PP.end
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        INNER JOIN hr_concept as HC
            ON HC.id = HPL.concept_id
        WHERE
            HP.state = 'paid' AND
            PP.end <= %(date_to)s AND
            PP.start >= %(date_from)s AND
            HP.contract_id = %(contract)s AND
            HC.code = %(concept_code)s
        ORDER BY PP.end DESC
        LIMIT 1
        """
        data = orm._fetchall(cr, query, param)
        if data:
            return data[0][0]
        return 0.0

    def get_variable_salary(self, cr, data, period, contract,
            categories=('earnings', 'comp_earnings', 'o_salarial_earnings')):
        self._get_total_concept_categories(cr, data, period, contract,
                                           exclude=('BASICO', 'PRIMA_CONV'), categories=categories)

    def get_last_year_prv_vac(self, data_payslip, date_to, audit=False, log={}):
        date_from = date_to - relativedelta(years=1) + relativedelta(days=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if data_payslip['contract'].fiscal_type_id.code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date
            
            if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
                date_from = data_payslip['contract'].apprentice_to_worker_date

        days = days360(date_from, date_to)
        data_payslip['last_year_prv'] = {
            'start': date_from.replace(day=1), 'end': date_to, 'days': days}
        leave_days = self.get_leave_no_pay(
            data_payslip['cr'], data_payslip['contract'].id, data_payslip['last_year_prv'])
        wd = days - leave_days
        data_payslip['last_year_prv']['worked_days'] = wd
        data = {}
        categories = ('earnings', 'o_salarial_earnings')
        if data_payslip['politics']['hr_payroll_co.include_comp_earnings_in_prv_vac']:
            categories = ('earnings', 'o_salarial_earnings', 'comp_earnings',)
        self.get_variable_salary(
            data_payslip['cr'], data, data_payslip['last_year_prv'], data_payslip['contract'].id, categories=categories)
        full_wage = data_payslip['contract'].get_wage(
            data_payslip['period'].end)['wage']
        average = full_wage
        for category in data:
            average += (data[category] / wd * 30)

        current_salary_variable = self._get_actual_variable_salary(
            data_payslip)
        if current_salary_variable:
            average += (current_salary_variable / wd * 30)

        conv_amounts = self._get_actual_conv_amount(
            data_payslip, data_payslip['last_year_prv'])
        if conv_amounts:
            average += (conv_amounts / wd * 30)

        retroactive_amount = self._get_current_retroactive(data_payslip, date_from, date_to)
        if retroactive_amount:
            average -= retroactive_amount * (1 if wd < 30 else 30/wd)

        if data_payslip['contract'].is_conventional:
            average += data_payslip['contract'].room_prima_amount

        data_payslip['last_year_prv']['average_prv'] = average / 30
        if audit:
            log['total_earnings'] = data.get("earnings", 0)
            log['total_comp_earnings'] = data.get("comp_earnings", 0)
            log['total_o_salarial_earnings'] = data.get(
                "o_salarial_earnings", 0)
            log['date_from'] = str(date_from)
            log['date_to'] = str(date_to)
            log['no_pay_leave_days'] = leave_days
            log['worked_days'] = wd
            log['total_base'] = data_payslip['last_year_prv']['average_prv']

    def get_last_year(self, data_payslip, date_to, audit=False, log={}):
        date_from = date_to - relativedelta(years=1) + relativedelta(days=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if data_payslip['contract'].fiscal_type_id.code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date
            
            if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
                date_from = data_payslip['contract'].apprentice_to_worker_date

        days = days360(date_from, date_to)
        data_payslip['last_year'] = {
            'start': date_from.replace(day=1), 'end': date_to, 'days': days}
        leave_days = self.get_leave_no_pay(
            data_payslip['cr'], data_payslip['contract'].id, data_payslip['last_year'])
        wd = days - leave_days
        data_payslip['last_year']['worked_days'] = wd
        data = {}
        self.get_variable_salary(
            data_payslip['cr'], data, data_payslip['last_year'], data_payslip['contract'].id)
        full_wage = data_payslip['contract'].get_wage(
            data_payslip['period'].end)['wage']
        average = full_wage
        for category in data:
            average += (data[category] / wd * 30)

        current_salary_variable = self._get_actual_variable_salary(
            data_payslip)
        if current_salary_variable:
            average += (current_salary_variable / wd * 30)

        conv_amounts = self._get_actual_conv_amount(
            data_payslip, data_payslip['last_year'])
        if conv_amounts:
            average += (conv_amounts / wd * 30)

        retroactive_amount = self._get_current_retroactive(data_payslip, date_from, date_to)
        if retroactive_amount:
            average -= retroactive_amount * (1 if wd < 30 else 30/wd)

        if data_payslip['contract'].is_conventional:
            average += data_payslip['contract'].room_prima_amount

        data_payslip['last_year']['average'] = average / 30
        if audit:
            log['total_earnings'] = data.get("earnings", 0)
            log['total_comp_earnings'] = data.get("comp_earnings", 0)
            log['total_o_salarial_earnings'] = data.get(
                "o_salarial_earnings", 0)
            log['date_from'] = str(date_from)
            log['date_to'] = str(date_to)
            log['no_pay_leave_days'] = leave_days
            log['worked_days'] = wd
            log['total_base'] = data_payslip['last_year']['average']

    def get_last_year_holidays(self, data_payslip, date_to, audit=False, log={}):
        date_from = date_to - relativedelta(years=1) + relativedelta(days=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start

        if data_payslip['contract'].fiscal_type_id.code == '19':
            labor_reform_start_date = self.get_labor_reform_start_date()
            if date_from < labor_reform_start_date:
                date_from = labor_reform_start_date

            if data_payslip['contract'].apprentice_to_worker_date and data_payslip['contract'].apprentice_to_worker_date > date_from:
                date_from = data_payslip['contract'].apprentice_to_worker_date

        days = days360(date_from, date_to)
        data_payslip['last_year_vac'] = {
            'start': date_from, 'end': date_to, 'days': days}
        leave_days = self.get_leave_no_pay(
            data_payslip['cr'], data_payslip['contract'].id, data_payslip['last_year_vac'])
        wd = days - leave_days
        data_payslip['last_year_vac']['worked_days'] = wd
        data = {}
        self.get_variable_salary(
            data_payslip['cr'], data, data_payslip['last_year_vac'], data_payslip['contract'].id)
        average = 0
        variable = 0
        for category in data:
            variable += data[category] * (1 if wd < 30 else 30/wd)
            average += data[category] * (1 if wd < 30 else 30/wd)

        retroactive_amount = self._get_current_retroactive(data_payslip, date_from, date_to)
        if retroactive_amount:
            average -= retroactive_amount * (1 if wd < 30 else 30/wd)
            variable -= retroactive_amount * (1 if wd < 30 else 30/wd)

        if variable:
            salary = 0
            months_salaries = data_payslip['contract'].average_wage_history_by_days(
                date_from, date_to)
            if months_salaries:
                for months in months_salaries.values():
                    salary += sum(months.values())
            average += salary * (30/wd)
        else:
            full_wage = data_payslip['contract'].get_wage(
                data_payslip['period'].end)['wage']
            average += full_wage

        data_payslip['last_year_vac']['average'] = average / 30
        if audit:
            log['total_earnings'] = data.get("earnings", 0)
            log['total_comp_earnings'] = data.get("comp_earnings", 0)
            log['total_o_salarial_earnings'] = data.get(
                "o_salarial_earnings", 0)
            log['date_from'] = str(date_from)
            log['date_to'] = str(date_to)
            log['no_pay_leave_days'] = leave_days
            log['worked_days'] = wd
            log['total_base'] = data_payslip['last_year_vac']['average']

    def get_holiday_book(self, data_payslip, date_to):
        data_payslip['holiday_book'] = data_payslip['contract'].get_holiday_book(
            data_payslip, date_to)

    def get_leave_no_pay(self, cr, contract, period):
        param = {
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        query = """
        SELECT count(*)
        FROM hr_leave_line as HLL
        INNER JOIN hr_leave as HL
            ON HL.id = HLL.leave_id
        INNER JOIN hr_leave_type as HLT
            ON HLT.id = HL.leave_type_id
        WHERE 
            HL.contract_id = %(contract)s AND
            HLL.date BETWEEN %(start)s AND %(end)s AND
            HLT.category_type = 'NO_PAY'
        """
        res = orm._fetchall(cr, query, param)
        return sum([x[0] for x in res if x[0]])

    def _get_actual_variable_salary(self, data_payslip):
        categories = ('earnings', 'comp_earnings', 'o_salarial_earnings')
        conv_cat = ('PRIMA_LIQ_CONV', 'PRIMA_VAC_CONV')
        sum_categories = sum([data_payslip.get(con, 0) for con in categories])
        sum_conv = sum([data_payslip.get(con, 0) for con in conv_cat])
        wage = 0
        if 'wage' in data_payslip:
            wage = data_payslip.get('wage')
            if type(wage) == dict:
                wage = wage.get('wage', 0)
        variable_salary = sum_categories - wage - sum_conv
        return variable_salary if variable_salary > 0 else 0

    def _get_actual_conv_amount(self, data_payslip, period):
        data = {}
        conv_cat = ('PRIMA_LIQ_CONV', 'PRIMA_VAC_CONV')
        sum_current_conv = sum([data_payslip.get(con, 0) for con in conv_cat])
        self._get_total_concept_by_code(
            data_payslip['cr'], data, period, data_payslip['contract'].id, codes=('PRIMA_CONV',))
        return sum_current_conv + sum(data.values())

    def _get_current_retroactive(self, data_payslip, date_from, date_to):
        lines = self.env['hr.novelty.line'].search([
            ('novelty_id.contract_id', '=', data_payslip['contract'].id),
            ('state', 'in', ('validated',)),
            ('novelty_id.novelty_type_id.use_by_default_retroactive', '=', True),
            ('period_id.start', '>=', date_from),
            ('period_id.end', '<=', date_to),
        ])
        return round(sum([x.amount for x in lines]))

    def _get_current_retroactive_paid(self, data_payslip):
        lines = self.env['hr.novelty.line'].search([
            ('novelty_id.contract_id', '=', data_payslip['contract'].id),
            ('state', 'in', ('paid',)),
            ('novelty_id.novelty_type_id.use_by_default_retroactive', '=', True),
            ('novelty_id.novelty_type_id.use_by_default_retroactive', '=', True),
            ('novelty_id.approve_date', '>=', data_payslip['date_from']),
            ('novelty_id.approve_date', '<=', data_payslip['date_to']),
        ])
        return round(sum([x.amount for x in lines]))

    def get_days_no_pay(self, data_payslip, query_params):
        leave_line = self.env['hr.leave.line']
        query_params['type'] = ('NO_PAY',)
        return leave_line.get_info_from_leave_type(data_payslip['cr'], query_params)[0]

    def _get_total_previous(self, data_payslip, date_from, date_to):
        concept = (self.code,)
        query_params = {
            'contract': data_payslip['contract'].id,
            'start': date_from,
            'end': date_to,
        }
        data_total = {}
        self._get_total_concepts(
            data_payslip['cr'], data_total, query_params, query_params['contract'], concept)
        return sum(data_total.values())

    def get_salary_in_leave(self, cr, data):
        """
        Construye el salario que se le debio pagar al empleado cuando estaba
        en incapacidad o vacaciones
        @params:
            cr: Cursor
            data: Dicionario con {'contract','start', 'end'}
        @return:
            int
        """
        query = """
        SELECT COALESCE(SUM(TMP.value_day), 0)  FROM(
            SELECT DISTINCT ON(HLL.date) HLL.date, WUH.wage/30 AS "value_day"
            FROM hr_leave_line AS  HLL
            INNER JOIN hr_leave AS HL ON HL.id=HLL.leave_id
            INNER JOIN hr_leave_type AS HLT ON HLT.id=HL.leave_type_id
            INNER JOIN wage_update_history AS WUH ON WUH.contract_id=HL.contract_id
            WHERE
                HL.contract_id = %(contract)s AND HLL.state in ('paid', 'validated') AND
                HLL.date BETWEEN %(start)s AND %(end)s AND
                HLT.category_type IN ('SICKNESS', 'AT_EP', 'VAC', 'PAY') AND
                HLL.date - WUH.date >= 0
                AND extract(day from HLL.date) < 31
                ORDER BY HLL.date, HLL.date - WUH.date) AS TMP"""
        return orm._fetchall(cr, query, data)[0][0]

    def _get_credit_account_concept(self, contract):
        type_class = contract.contract_type_id.type_class
        section = contract.contract_type_id.section
        account_field_name = f'{type_class}_{section}_credit'
        account = getattr(self, account_field_name)
        return account

    def get_general_ibc(self, data_payslip, apply_25_smmlv_cap=True):
        current_salarial = 0
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]

        categories = ('earnings', 'o_salarial_earnings',
                      'comp_earnings', 'o_rights')
        if self.code == 'PRV_VAC' and not data_payslip['politics']['hr_payroll_co.include_comp_earnings_in_prv_vac']:
            categories = ('earnings', 'o_salarial_earnings', 'o_rights')
        for category in categories:
            current_salarial += data_payslip.get(category, 0)

        exclude = ('PRIMA', 'PRIMA_LIQ', 'VAC_LIQ')
        for ex in exclude:
            current_salarial -= data_payslip.get(ex, 0)

        current_non_salarial = data_payslip.get('o_earnings', 0)

        period = {
            'start': data_payslip['period'].end.replace(day=1),
            'end': data_payslip['period'].end
        }
        categories_amounts = {}
        self._get_total_concept_categories(
            self._cr, categories_amounts, period, data_payslip['contract'].id, categories=categories, exclude=exclude)
        previous_non_salarial = categories_amounts.get('o_earnings', 0)
        previous_salarial = sum(
            categories_amounts.values()) - previous_non_salarial
        
        if (data_payslip['contract'].fiscal_type_id.code == '19'
                and data_payslip['contract'].apprentice_to_worker_date
                and data_payslip['contract'].apprentice_to_worker_date >= data_payslip['period'].start
                and data_payslip['contract'].apprentice_to_worker_date <= data_payslip['period'].end):
            months_salaries = data_payslip['contract'].average_wage_history_by_days(
                data_payslip['contract'].apprentice_to_worker_date, data_payslip['period'].end)
            if months_salaries:
                previous_salarial = 0
                for salary in months_salaries.values():
                    current_salarial = sum(salary.values())

        o_earnings = current_non_salarial + previous_non_salarial
        salary = current_salarial + previous_salarial

        # Incapacidades con valor 0
        query = '''
            SELECT COALESCE(count(*), 0)
            FROM hr_leave_line AS HLL
            INNER JOIN hr_leave AS HL
                ON HL.id = HLL.leave_id
            INNER JOIN hr_leave_type AS HLT
                ON HLT.id = HL.leave_type_id
            WHERE 
                HL.contract_id = %(contract)s AND 
                HLL.amount = 0 AND 
                HLT.category_type = 'SICKNESS' AND
                HLL.state = 'validated' AND
                HLL.date BETWEEN %(start)s AND %(end)s
        '''
        params = {
            'contract': data_payslip['contract'].id,
            'start': data_payslip['period'].start,
            'end': data_payslip['period'].end
        }
        sickness_days_worthless = orm._fetchall(self._cr, query, params)[0][0]
        if sickness_days_worthless:
            wage_history = self.env['wage.update.history'].search([
                ('contract_id', '=', data_payslip['contract'].id),
                ('date', '<=', data_payslip['period'].end)
            ])
            current_wage = max(wage_history, key=lambda x: x.date)
            salary += current_wage.wage * sickness_days_worthless / 30

        top40 = (salary + o_earnings) * 0.4
        ibc_int_vac = 0
        if o_earnings > top40:
            ibc = salary + o_earnings - top40
        else:
            ibc = salary

        if data_payslip['contract'].contract_type_id.type_class == 'int':
            ibc_int_vac = ibc
            ibc *= 0.7

        if apply_25_smmlv_cap and ibc > 25 * smmlv:
            ibc = 25 * smmlv

        return ibc, ibc_int_vac

    ############################################################################
    # ------------------- CALCULO DE CONCEPTOS INDIVIDUALES -------------------#
    ############################################################################

    def _SUB_TRANS(self, data_payslip):
        sena_lec = data_payslip['contract'].fiscal_type_id.code == '12'
        days_sena_lec = 0
        skip_sub_trans = data_payslip['contract'].skip_commute_allowance
        if sena_lec or skip_sub_trans:
            return

        sena_prod = data_payslip['contract'].fiscal_type_id.code in (
            '19', '23')
        pays_sub_trans_train_prod = data_payslip['politics']['hr_payroll_co.pays_sub_trans_train_prod']
        pay_sub_trans_in_q2 = data_payslip['politics']['hr_payroll_co.pay_sub_trans_in_q2']
        if sena_prod and not pays_sub_trans_train_prod:
            return
        if (sena_prod and data_payslip['contract'].apprentice_to_worker_date
                and data_payslip['contract'].apprentice_to_worker_date >= data_payslip['period'].start
                and data_payslip['contract'].apprentice_to_worker_date <= data_payslip['period'].end):
            days_sena_lec += (data_payslip['contract'].apprentice_to_worker_date -
                              data_payslip['period'].start).days

        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['current_year_month']]
        threshold = 2 * smmlv

        contract_start = data_payslip['contract'].date_start
        period_start = data_payslip['period'].start
        date_ref = contract_start if contract_start > period_start else period_start
        wage = data_payslip['contract'].get_wage(date_ref)['wage']
        if wage > threshold:
            return

        # Get payslip concept
        if data_payslip['contract'].remote_work_allowance:
            sub_conne = self.env.ref('hr_payroll_co.hc_sub_conne')
            name = sub_conne.name
            concept_id = sub_conne.id
        else:
            name = self.name
            concept_id = self.id

        # Get threshold
        is_biweekly = data_payslip['period'].type_period == 'BIWEEKLY'
        is_q1 = is_biweekly and data_payslip['period'].type_biweekly == 'FIRST'
        if is_q1:
            if pay_sub_trans_in_q2:
                return
            threshold /= 2

        # Get earnings
        earnings = data_payslip.get('earnings', 0)
        earnings += data_payslip.get(TPCT, {}).get('earnings', 0)

        # Get previous
        total_previous = {}
        concepts = ('SUB_TRANS', 'SUB_CONNE')
        payment_period = {
            'start': data_payslip['period'].end.replace(day=1),
            'end': data_payslip['period'].end
        }
        if is_biweekly and not is_q1 and not pay_sub_trans_in_q2:
            payment_period['start'] = data_payslip['period'].start
        self._get_total_concepts(
            data_payslip['cr'], total_previous, payment_period, data_payslip['contract'].id, concepts)
        sub_trans_paid = total_previous.get('SUB_TRANS', 0)
        sub_conne_paid = total_previous.get('SUB_CONNE', 0)
        already_paid = sub_trans_paid + sub_conne_paid

        sub_trans = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['current_year_month']] / 30
        if is_biweekly and is_q1 and data_payslip['politics']['hr_payroll_co.sub_trans_q1_with_incomes']:
            earnings += wage / 2
            threshold *= 2
        if earnings <= threshold:
            query = '''
            SELECT COALESCE(SUM(HPL.qty), 0) AS qty
            FROM hr_payslip_line AS HPL
            INNER JOIN hr_payslip AS HP
                ON  HP.id = HPL.payslip_id
            INNER JOIN hr_period AS PP
                ON PP.id = HP.period_id
            LEFT JOIN
                hr_concept AS hc ON hc.id = HPL.concept_id
            WHERE 
                HP.contract_id = %(contract)s AND
                PP.start < %(end)s AND PP.end > %(start)s AND
                HP.state = 'paid' AND 
                (HPL.name = 'SUELDO BASICO' OR hc.name = 'SUELDO BASICO')
            '''
            param = {
                'contract': data_payslip['contract'].id,
                'start': data_payslip['period'].start.replace(day=1),
                'end': data_payslip['period'].end,
            }
            if is_biweekly and not is_q1 and not pay_sub_trans_in_q2:
                param['start'] = data_payslip['period'].start
            days_already_worked = orm._fetchall(
                data_payslip['cr'], query, param)[0][0]

            current_worked_days = data_payslip.get('BASICO', (0, 0))[1]
            worked_days = current_worked_days + days_already_worked - days_sena_lec
            total_global = sub_trans * worked_days
            total = total_global - already_paid
            data_payslip[self.code] = total
            data_payslip['SUB_TRANS'] = total

            if days_sena_lec > 0:
                qty = worked_days
            else:
                qty = worked_days if total > sub_trans * 15 else current_worked_days

            return {
                'name': name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': sub_trans,
                'qty': qty,
                'rate': 100,
                'total': total,
                'origin': 'local',
                'concept_id': concept_id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
            }
        elif already_paid:
            return_amount = -already_paid
            data_payslip[self.code] = -return_amount
            data_payslip['SUB_TRANS'] = -return_amount
            return {
                'name': name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': return_amount,
                'qty': 1,
                'rate': 100,
                'total': return_amount,
                'origin': 'local',
                'concept_id': concept_id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
            }

    def _IBD(self, data_payslip):
        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['IBD'],
            'qty': 1,
            'rate': 100,
            'total': data_payslip['IBD'],
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _DED_EPS(self, data_payslip):
        is_sena = data_payslip['contract'].contract_type_id.type_class == 'apr'
        if is_sena:
            if not self._apply_labor_reform(data_payslip):
                return

            if data_payslip['contract'].fiscal_type_id.code != '19':
                return

        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)
        rate = data_payslip['politics']['hr_payroll_co.eps_rate_employee']
        apply_prim_conv = data_payslip['politics']['hr_payroll_co.apply_prim_conv']
        if apply_prim_conv and data_payslip['contract'].is_conventional:
            rate = data_payslip['politics']['hr_payroll_co.percentage_ded_eps_conv']
        total = data_payslip['IBD'] * rate / 100
        if data_payslip['politics']['hr_payroll_co.does_not_allow_ibd_less_than_smmlv']:
            total, value = self._compute_base_less_tham_smmlv(
                data_payslip, rate)
        else:
            value = data_payslip['IBD']
            total = data_payslip['IBD'] * rate / 100
        total -= data_payslip.get(TPCP, {}).get('DED_EPS', 0)
        data_payslip['DED_EPS'] = total

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': value,
            'qty': 1,
            'rate': rate,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _INDEM(self, data_payslip):
        logs = self._initialize_logs(data_payslip)
        if 'INDEM_value' not in data_payslip or 'INDEM_qty' not in data_payslip:
            self._compute_indem(data_payslip, True, logs)
        value = data_payslip.get('INDEM_value', 0)
        qty = data_payslip.get('INDEM_qty', 0)
        if value == 0 or qty == 0:
            return
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': value,
            'qty': qty,
            'rate': 100,
            'total': value * qty,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
            'log_ids': logs
        }

    def _RTF_INDEM(self, data_payslip):
        if 'INDEM_value' not in data_payslip or 'INDEM_qty' not in data_payslip:
            self._compute_indem(data_payslip)
        value = data_payslip.get('INDEM_value', 0)
        qty = data_payslip.get('INDEM_qty', 0)
        uvt = data_payslip['economic_variables']['UVT'][data_payslip['current_year_month']]
        if value * 30 <= 204 * uvt:
            return
        value *= qty * 0.75
        rate = 20
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': value,
            'qty': 1,
            'rate': rate,
            'total': value * rate / 100,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _NETO_CES(self, data_payslip):
        ces_codes = ['CES']
        total = sum([round(data_payslip.get(code, 0)) for code in ces_codes])

        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': total,
            'qty': 1,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _NETO(self, data_payslip):
        total_earnings = ['earnings', 'o_salarial_earnings',
                          'comp_earnings', 'o_rights', 'o_earnings', 'non_taxed_earnings']
        total_deductions = ['deductions']
        total = 0
        for te in total_earnings:
            total += round(data_payslip.get(te, 0))
        for td in total_deductions:
            total -= round(data_payslip.get(td, 0))

        ces_codes = ['CES']
        total -= sum([round(data_payslip.get(code, 0)) for code in ces_codes])
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': total,
            'qty': 1,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _NETO_LIQ(self, data_payslip):
        total_earnings = ['earnings', 'o_salarial_earnings',
                          'comp_earnings', 'o_rights', 'o_earnings', 'non_taxed_earnings']
        total_deductions = ['deductions']
        total = 0
        for te in total_earnings:
            total += round(data_payslip.get(te, 0))
        for td in total_deductions:
            total -= round(data_payslip.get(td, 0))

        ces_codes = ['CES']
        total -= sum([round(data_payslip.get(code, 0)) for code in ces_codes])
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': total,
            'qty': 1,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }
