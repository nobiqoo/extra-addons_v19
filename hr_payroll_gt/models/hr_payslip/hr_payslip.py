# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.addons.utilities_collection import orm

from .hr_concept import CONCEPTS_GT

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_slip_gt(self, _cr=False):
        data_to_remove = {
            'hr.payslip.line': [],
            'hr.payslip.day': [],
            'hr.payslip.line.log': []
        }
        data_to_create = {
            'hr.payslip.line': [],
            'hr.payslip.day': [],
            'hr.payslip.line.log': []
        }
        sorted_concepts = {}
        categories_novelty = {}
        economic_variables = {
            'SMMLV': {},
        }
        global_error_log = ''
        politics = self._get_politics_gt()
        total_previous = {}
        total_concepts = {}
        # self._get_categories_search(
        #     total_previous,
        #     self[0].period_id.start.replace(day=1),
        #     self[0].period_id.end)
        # self._get_concepts_search(
        #     total_concepts,
        #     self[0].period_id.start.replace(day=1),
        #     self[0].period_id.end)
        cr = orm.create_cursor(self._cr)
        len_self = len(self)
        value_eval = int(len_self/10) if int(len_self/10) > 0 else 1
        for i, record in enumerate(self):
            if i % value_eval == 0:
                orm.log_message(f'Calculando {i+1} de {len_self} Nóminas')
            record.error_log = ''
            record.payslip_type_id.get_sorted_concepts_gt(sorted_concepts)
            record.payslip_type_id.get_categories_novelty_gt(categories_novelty)
            payslip_line_novelty = []
            payslip_day_ids = []
            payslip_line_concept = []
            payslip_line_log = []
            try:
                record.evaluate_constraints()
                if not economic_variables:
                    economic_variables = record.build_economic_variables()
            except ValidationError as ex:
                global_error_log += record.create_error_log(ex.__str__())
                continue

            data_to_remove['hr.payslip.line'] += record.payslip_line_ids.ids
            data_to_remove['hr.payslip.day'] += record.payslip_day_ids.ids
            data_to_remove['hr.payslip.line.log'] += record.log_ids.ids

            # Contexto de la nomina
            data_payslip = record.create_data_payslip(
                economic_variables, politics, total_previous, total_concepts, cr)

            # Liquida Prestamos
            if record.payslip_type_id.category == 'LIQ':
                record._compute_liquidation_loan()

            # Novedades, Horas Extras, Ausencias
            record.compute_payslip_novelty_gt(
                payslip_line_novelty, payslip_day_ids, data_payslip, categories_novelty)
            data_to_create['hr.payslip.line'] += payslip_line_novelty

            # Dias de Nómina
            record.set_no_leave_days(payslip_day_ids)
            data_payslip['payslip_days'] = payslip_day_ids
            data_to_create['hr.payslip.day'] += payslip_day_ids

            # Conceptos de Nómina
            error_log = record.compute_payslip_line_concept_gt(
                payslip_line_concept, payslip_line_log, data_payslip, sorted_concepts)
            if error_log:
                global_error_log += error_log
            data_to_create['hr.payslip.line'] += payslip_line_concept
            data_to_create['hr.payslip.line.log'] += payslip_line_log

        for d2r in data_to_remove:
            orm.delete(self._cr, self.env.uid, d2r,
                       {'id': data_to_remove[d2r]}, cr_aux=_cr)
        for d2c in data_to_create:
            orm.create(self._cr, self.env.uid, d2c,
                       data_to_create[d2c], progress=True, cr_aux=_cr)
        return global_error_log

    def compute_payslip_line_concept_gt(self, payslip_line_concept, payslip_line_log, data_payslip, sorted_concepts):
        for concept_id in sorted_concepts[self.payslip_type_id.id]:
            # Los aportes se calculan en PILA
            if concept_id.category == 'contributions':
                continue
            if concept_id.code not in CONCEPTS_GT:
                continue
            try:
                payslip_line = eval(
                    'concept_id._' + concept_id.code + '(data_payslip)')
                if type(payslip_line) == dict:
                    if concept_id.code == 'PRV_VAC':
                        payslip_line['total'] = payslip_line['total']
                    else:
                        payslip_line['total'] = round(payslip_line['total'], 2)
                    self.update_data_payslip(data_payslip, payslip_line)
                    payslip_line_concept.append(payslip_line)

                    if 'log_ids' in payslip_line:
                        payslip_line_log.append(payslip_line['log_ids'])
                        del payslip_line['log_ids']

                # Calcula novedades que dependen de dias trabajados
                if concept_id.code == 'BASICO':
                    worked_days = payslip_line['qty']
                    max_working_days = 30 if self.period_id.type_period == 'MONTHLY' else 15
                    for novelty_line in data_payslip.get('hr.novelty.line.dep_days_worked', []):
                        novelty_payslip_line = novelty_line.create_payslip_line_dep_days_worked(
                            data_payslip, worked_days, max_working_days)
                        novelty_payslip_line['total'] = round(
                            novelty_payslip_line['total'], 2)
                        self.update_data_payslip(
                            data_payslip, novelty_payslip_line)
                        payslip_line_concept.append(novelty_payslip_line)

            except ValidationError as ex:
                return self.create_error_log(ex.__str__())

    def to_paid_gt(self):
        account_move = self.env['account.move']
        move_lines = []
        move_ids = []
        payslip_ids = []
        for record in self:
            if record.state != 'draft':
                continue
            payslip_ids.append(record.id)
            if not record.payslip_line_ids:
                name = record.name
                raise ValidationError(
                    f'La nómina {name} no tiene conceptos que causar.')
            record.error_log = ''
            new_move = {
                'date': record.accounting_date,
                'currency_id': record.company_id.currency_id.id,
                'journal_id': record.journal_id.id,
                'move_type': 'entry',
                'state': 'draft',
                'partner_id': record.contract_id.employee_id.partner_id.id,
                'auto_post': 'no',
                'invoice_currency_rate': 1.0
            }
            move_id = account_move.create(new_move)
            move_ids.append(move_id.id)
            contract_type = record.contract_id.contract_type_id
            prefix_account = f'{contract_type.type_class}_{contract_type.section}_'
            for payslip_line in record.payslip_line_ids:
                tax_id = False
                tax_base_amount = 0
                if payslip_line.concept_id.apply_tax_base and payslip_line.concept_id.tax_id:
                    tax_id = payslip_line.concept_id.tax_id.id
                    tax_base_amount = payslip_line.value
                if payslip_line.concept_id:
                    obj_base = payslip_line.concept_id
                elif payslip_line.leave_id:
                    if payslip_line.is_rest_or_dayoff:
                        obj_base = payslip_line.leave_id.holidays_leave_type_id
                    else:
                        obj_base = payslip_line.leave_id.leave_type_id
                elif payslip_line.novelty_id:
                    obj_base = payslip_line.novelty_id.novelty_type_id
                elif payslip_line.overtime_id:
                    obj_base = payslip_line.overtime_id.overtime_type_id
                else:
                    record.error_log = f'La línea de nómina {payslip_line.name} de {record.name} no esta configurada correctamente'
                    break
                partner_id = obj_base.get_partner_id(record.contract_id)

                neto_code = ['NETO_GT', 'NETO_CES', 'NETO_LIQ']

                if payslip_line.category in ['earnings', 'o_salarial_earnings', 'comp_earnings',
                                             'o_rights', 'o_earnings', 'non_taxed_earnings']:
                    accounts = ['debit']
                elif payslip_line.category == 'deductions' or (payslip_line.category == 'subtotals' and payslip_line.concept_id.code in neto_code):
                    accounts = ['credit']
                elif payslip_line.category == 'provisions':
                    accounts = ['credit', 'debit']
                else:
                    continue

                for acc in accounts:
                    if payslip_line.total > 0:
                        if acc == 'debit':
                            debit_credit = {
                                'debit': payslip_line.total, 'credit': 0}
                        else:
                            debit_credit = {
                                'debit': 0, 'credit': payslip_line.total}
                    elif payslip_line.total < 0:
                        if acc != 'debit':
                            debit_credit = {
                                'debit': -payslip_line.total, 'credit': 0}
                        else:
                            debit_credit = {
                                'debit': 0, 'credit': -payslip_line.total}
                    else:
                        continue
                    account = getattr(obj_base, prefix_account + acc)
                    if not account:
                        raise ValidationError(
                            f'La línea de nómina {payslip_line.name} de {record.name} no tiene cuentas contables configuradas')
                    analytic_distribution = record._get_distribution(account)
                    new_move_line = {
                        'account_id': account.id,
                        'partner_id': partner_id,
                        'name': payslip_line.name,
                        'move_id': move_id.id,
                        'currency_id': record.company_id.currency_id.id,
                        'analytic_distribution': analytic_distribution,
                        'tax_line_id': tax_id,
                        'tax_base_amount': tax_base_amount
                    }
                    new_move_line.update(debit_credit)
                    move_lines.append(new_move_line)
            record.write({'move_id': move_id.id, 'state': 'paid'})
            record.contract_id.add_to_holiday_book(record)

        self.env['account.move.line'].create(move_lines)
        self.env['account.move'].browse(move_ids).action_post()
        domain = [('payslip_id', 'in', payslip_ids)]
        for model, parent in [('hr.leave.line', 'leave_id'), ('hr.novelty.line', 'novelty_id'), ('hr.overtime', None)]:
            lines_ids = self.env[model].search(domain)
            lines_ids.write({'state': 'paid'})

            if parent:
                parent_ids = {getattr(l, parent) for l in lines_ids}
                [p.to_paid() for p in parent_ids]

    def _get_politics_gt(self):
        model = 'ir.config_parameter'
        politics = {
            'hr_payroll_gt.assumed_disability_february_gt': bool,
            'hr_payroll_gt.pay_advance_vacation_gt': bool,
            'hr_payroll_gt.deductions_with_previous_ibc_gt': bool,
            'hr_payroll_gt.does_not_allow_ibd_less_than_smmlv_gt': bool,
            'hr_payroll_gt.percentage_igss': float,
            'hr_payroll_gt.rate_prv_agu_gt': float,
            'hr_payroll_gt.rate_prv_bon_14': float,
            'hr_payroll_gt.rate_prv_vac_gt': float,
            'hr_payroll_gt.rate_prv_ind_gt': float,
            'hr_payroll_gt.rate_prv_cuo_pat': float,
        }
        for param in politics:
            politics[param] = (politics[param])(
                self.env[model].sudo().get_param(param))
        return politics

    def compute_payslip_novelty_gt(self, payslip_line_novelty, payslip_day_ids, data_payslip, categories_novelty):
        pay_advance_vacation = data_payslip['politics']['hr_payroll_gt.pay_advance_vacation_gt']
        assumed_disability_february = data_payslip['politics']['hr_payroll_gt.assumed_disability_february_gt']
        domain_vac = [
            ('state', 'in', ('validated', 'paid')),
            ('contract_id', '=', self.contract_id.id),
            ('period_id.start', '>=', self.period_id.start),
            ('leave_id.category_type', '=', 'VAC')
            ]
        domain_not_vac = [
            ('state', '=', 'validated'),
            ('period_id', '=', self.period_id.id),
            ('contract_id', '=', self.contract_id.id),
            ('leave_id.category_type', '!=', 'VAC')
            ]
        domain = [('state', '=', 'validated'),
                  ('period_id', '=', self.period_id.id),
                  ('contract_id', '=', self.contract_id.id)]
        categories = categories_novelty.get(self.payslip_type_id.id, {})
        wage = data_payslip['wage'].get('wage', 0) / 30
        key = 'value_total_leave'
        for model in ['hr.novelty.line', 'hr.leave.line', 'hr.overtime']:
            if model not in categories:
                continue
            if model == 'hr.leave.line' and pay_advance_vacation:
                payslip_novelty_ids = self.env[model].search(domain_vac)
                payslip_novelty_ids += self.env[model].search(domain_not_vac)
            else:
                payslip_novelty_ids = self.env[model].search(domain)
            for payslip_novelty in payslip_novelty_ids:
                if not payslip_novelty.belongs_category(categories[model]):
                    continue
                # Descarta novedades que dependen de dias trabajados, se calcula post calculo de basico
                if model == 'hr.novelty.line' and payslip_novelty.novelty_id.novelty_type_id.dep_days_worked:
                    if 'hr.novelty.line.dep_days_worked' in data_payslip:
                        data_payslip['hr.novelty.line.dep_days_worked'].append(
                            payslip_novelty)
                    else:
                        data_payslip['hr.novelty.line.dep_days_worked'] = [
                            payslip_novelty]
                    continue

                if model == 'hr.leave.line' and payslip_novelty.leave_id.category_type != 'VAC_MONEY':
                    if payslip_novelty.period_id.id == self.period_id.id:
                        payslip_day_ids.append(
                            {'payslip_id': self.id, 'day': payslip_novelty.date.day, 'day_type': 'A'})
                    if payslip_novelty.leave_id.category_type in ['SICKNESS', 'AT_EP', 'NO_PAY', 'PAY', 'VAC']:
                        data_payslip[key] = data_payslip.get(key, 0) + wage
                elif model == 'hr.novelty.line':
                    payslip_novelty.check_modality_rtefte(data_payslip)
                if payslip_novelty.state == 'paid' and pay_advance_vacation:
                    continue
                # Borrar conceptos de otras nominas
                payslip_novelty.payslip_id = self.id
                new_payslip_line = payslip_novelty.create_payslip_line(self.id)
                create = True
                for payslip_line in payslip_line_novelty:
                    if payslip_line['unique_key'] == new_payslip_line['unique_key']:
                        create = False
                        if 'leave_id' in payslip_novelty:
                            if payslip_novelty.leave_id.category_type != 'VAC_MONEY':
                                payslip_line['qty'] += new_payslip_line['qty']
                                if (assumed_disability_february and data_payslip['period'].end.month == 2
                                        and data_payslip['period'].end.day == payslip_novelty.date.day
                                        and payslip_novelty.leave_id.category_type in ('MAT_LIC', 'PAT_LIC')):
                                    payslip_line['qty'] += (30 - data_payslip['period'].end.day)
                                    payslip_line['total'] += new_payslip_line['total'] * (30 - data_payslip['period'].end.day)
                            else:
                                payslip_line['qty'] = new_payslip_line['qty']
                        else:
                            payslip_line['qty'] = new_payslip_line['qty']
                        payslip_line['total'] += new_payslip_line['total']
                        break
                if create:
                    payslip_line_novelty.append(new_payslip_line)
        for payslip_line in payslip_line_novelty:
            payslip_line['total'] = round(payslip_line['total'], 2)
            self.update_data_payslip(data_payslip, payslip_line)
            if 'unique_key' in payslip_line:
                payslip_line.pop('unique_key')
