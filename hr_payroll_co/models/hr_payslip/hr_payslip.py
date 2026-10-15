# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from odoo.addons.utilities_collection import orm
from odoo.addons.hr_payroll_co.models.hr_concept.hr_concept_base import CONCEPTS, TPCT, TPCP

STATE = [
    ('draft', 'Borrador'),
    ('paid', 'Pagada')
]

CATEGORIES_SEARCH = ['earnings', 'o_salarial_earnings', 'comp_earnings',
                     'o_rights', 'o_earnings', 'deductions']

CONCEPTS_SEARCH = ['PRIMA', 'PRIMA_LIQ', 'DED_PENS',
                   'DED_EPS', 'FOND_SOL', 'FOND_SUB', 'RTEFTE']

MAIL_TEMPLATE = "hr_payroll_co.hr_payroll_co_mail_template"

EG_GENERAL_SICKNESS_CODES = ('EG_B2', 'EG_B90', 'EG_B180', 'EG_A180')
EG_GENERAL_TO_COMPLEMENT_CODE = {
    'EG_B2': 'EG_B2_COMP',
    'EG_B90': 'EG_B90_COMP',
    'EG_B180': 'EG_B180_COMP',
    'EG_A180': 'EG_A180_COMP',
}


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _description = 'Nómina'
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Selection(
        string='Estado', selection=STATE, default='draft', index=True)

    contract_id = fields.Many2one(comodel_name='hr.contract', string='Contrato',
                                  domain="[('state','=','open')]", required=True,
                                  check_company=True, index=True)
    employee_id = fields.Many2one(comodel_name='hr.employee',
                                  string='Empleado',
                                  check_company=True, index=True)

    liquidation_date = fields.Date(string='Fecha de Liquidación')
    accounting_date = fields.Date(string='Fecha de Contabilización')
    cutoff_date = fields.Date(string='Fecha de corte')
    mail_sended = fields.Boolean("Correo enviado", default=False)
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo', domain=[('active', '=', True)], required=True,
        check_company=True, index=True)
    payslip_type_id = fields.Many2one(
        comodel_name='hr.payslip.type', string='Tipo de Nómina', required=True,
        check_company=True, index=True)
    payslip_type_category = fields.Selection(
        string='Categoría del tipo de nómina',
        related='payslip_type_id.category', readonly=True)
    payslip_processing_id = fields.Many2one(
        comodel_name='hr.payslip.processing', string='Procesamiento de Nómina',
        index=True)
    error_log = fields.Text(string='Errores', readonly=True)
    journal_id = fields.Many2one(
        comodel_name='account.journal', string='Diario', required=True,
        check_company=True)
    move_id = fields.Many2one(
        comodel_name='account.move', string='Asiento contable', readonly=True)

    payslip_day_ids = fields.One2many(
        comodel_name='hr.payslip.day', inverse_name='payslip_id', string='Días de Nómina', readonly=True)
    payslip_line_ids = fields.One2many(
        comodel_name='hr.payslip.line', inverse_name='payslip_id', string='Conceptos de Nómina')
    earnings_ids = fields.One2many(
        comodel_name='hr.payslip.line', compute="_compute_concepts_category", string='Conceptos de Nómina / Devengos')
    deductions_ids = fields.One2many(
        comodel_name='hr.payslip.line', compute="_compute_concepts_category", string='Conceptos de Nómina / Deducciones')
    provisions_ids = fields.One2many(
        comodel_name='hr.payslip.line', compute="_compute_concepts_category", string='Conceptos de Nómina / Provisiones')
    outcome_ids = fields.One2many(
        comodel_name='hr.payslip.line', compute="_compute_concepts_category", string='Conceptos de Nómina / Totales')
    log_ids = fields.One2many(
        comodel_name='hr.payslip.line.log', string='Logs', inverse_name='payslip_id')
    location_code = fields.Char(
        string='Código de localización', compute='_compute_location_code', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'seq.hr.payslip') or ''
        return super(HrPayslip, self).create(vals_list)

    def write(self, vals):
        if 'error_log' not in vals:
            vals['error_log'] = ''
        if vals.get('mail_sended', False):
            del vals['mail_sended']
        if 'mail_sended_internal' in vals:
            vals['mail_sended'] = vals['mail_sended_internal']
            del vals['mail_sended_internal']
        return super(HrPayslip, self).write(vals)

    def unlink(self):
        payslip_remove = [x.id for x in self if x.state == 'draft']
        orm.delete(self._cr, self.env.uid,
                   'hr.payslip.line', {'payslip_id': payslip_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.payslip.line.log', {'payslip_id': payslip_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.payslip.day', {'payslip_id': payslip_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.payslip', {'id': payslip_remove})

    @api.depends('company_id.chart_template')
    def _compute_location_code(self):
        for record in self:
            record.location_code = record.company_id.chart_template

    @api.depends('payslip_line_ids')
    def _compute_concepts_category(self):
        for record in self:
            earnings = []
            deductions = []
            provisions = []
            outcome = []
            for payslip_line in record.payslip_line_ids:
                if payslip_line.category in ['earnings', 'o_salarial_earnings', 'comp_earnings',
                                             'o_rights', 'o_earnings', 'non_taxed_earnings']:
                    earnings.append(payslip_line.id)
                elif payslip_line.category == 'deductions':
                    deductions.append(payslip_line.id)
                elif payslip_line.category == 'provisions':
                    provisions.append(payslip_line.id)
                else:
                    outcome.append(payslip_line.id)
            record.earnings_ids = self.env['hr.payslip.line'].browse(
                earnings)
            record.deductions_ids = self.env['hr.payslip.line'].browse(
                deductions)
            record.provisions_ids = self.env['hr.payslip.line'].browse(
                provisions)
            record.outcome_ids = self.env['hr.payslip.line'].browse(
                outcome)

    def _get_employee(self):
        for record in self:
            if record.contract_id:
                if not record.contract_id.employee_id:
                    raise ValidationError(
                        'El contrato %s no tiene un emplado relacionado' % self.contract_id.name)
                record.employee_id = record.contract_id.employee_id
            else:
                record.employee_id = False

    @api.onchange('employee_id')
    def _get_contract(self):
        for record in self:
            if not record.employee_id:
                record.contract_id = False
                continue
            if record.contract_id and record.contract_id.employee_id.id == record.employee_id.id:
                continue

            contract_id = self.env['hr.contract'].search(
                [('employee_id', '=', record.employee_id.id), ('state', '=', 'open')])
            if not contract_id:
                raise ValidationError(
                    'El emplado %s no tiene contrato en proceso' % (record.employee_id.name))
            if len(contract_id) > 1:
                raise ValidationError('El emplado %s tiene %s contratos en proceso' % (
                    record.employee_id.name, len(contract_id)))
            record.contract_id = contract_id

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        self._get_employee()
        res = {
            'value': {
                'period_id': False,
            },
            'domain': {
                'period_id': [('type_period', '=', self.contract_id.schedule_pay), ('active', '=', True)],
            },
        }
        return res

    def _get_politics(self):
        model = 'ir.config_parameter'
        politics = {
            'hr_payroll_co.pays_sub_trans_train_prod': bool,
            'hr_payroll_co.eps_rate_employee': float,
            'hr_payroll_co.pen_rate_employee': float,
            'hr_payroll_co.discount_suspensions': bool,
            'hr_payroll_co.average_sub_trans': bool,
            'hr_payroll_co.compute_simple_provisions': bool,
            'hr_payroll_co.holidays_percentage': float,
            'hr_payroll_co.prima_percentage': float,
            'hr_payroll_co.severance_percentage': float,
            'hr_payroll_co.interest_severance_percentage': float,
            'hr_payroll_co.social_benefits_with_last_wage': bool,
            'hr_payroll_co.deductions_with_previous_ibc': bool,
            'hr_payroll_co.does_not_allow_ibd_less_than_smmlv': bool,
            'hr_payroll_co.average_prima_in_settlement_less_than_month': bool,
            'hr_payroll_co.discount_all_leave_in_social_benefits': bool,
            'hr_payroll_co.accumulated_minimum_top_40': bool,
            'hr_payroll_co.pay_sub_trans_in_q2': bool,
            'hr_payroll_co.pay_advance_vacation': bool,
            'hr_payroll_co.assumed_disability_february': bool,
            'hr_payroll_co.apply_prim_conv': bool,
            'hr_payroll_co.days_in_prim_conv': float,
            'hr_payroll_co.days_in_prim_vac_conv': float,
            'hr_payroll_co.percentage_prv_prim_conv': float,
            'hr_payroll_co.percentage_prv_prim_liq_conv': float,
            'hr_payroll_co.percentage_ded_eps_conv': float,
            'hr_payroll_co.apply_no_pay_leave_intces': bool,
            'hr_payroll_co.total_avg_holidays': bool,
            'hr_payroll_co.dont_apply_labor_reform': bool,
            'hr_payroll_co.sub_trans_q1_with_incomes': bool,
            'hr_payroll_co.apply_no_pay_leave_ces': bool,
            'hr_payroll_co.prima_avg_variable': bool,
            'hr_payroll_co.pays_eg_general_complement': bool,
            'hr_payroll_co.assumed_pen_not_remunerate_licences': bool,
            'hr_payroll_co.include_comp_earnings_in_prv_vac': bool,
            'hr_payroll_co.intces_days_with_last_page': bool,
        }
        for param in politics:
            politics[param] = (politics[param])(
                self.env[model].sudo().get_param(param))
        politics['hr_payroll_co.percentage_prv_nav'] = self.env.company.percentage_prv_nav or 0.0
        politics['hr_payroll_co.percentage_prv_day_31'] = self.env.company.percentage_prv_day_31 or 0.0
        politics['hr_payroll_co.percentage_prv_aux_vac'] = self.env.company.percentage_prv_aux_vac or 0.0
        politics['hr_payroll_co.percentage_prv_old'] = self.env.company.percentage_prv_old or 0.0
        return politics

    def _check_concepts_belonging(self, concepts):
        compute = False
        blacklits = []
        for record in self:
            if record.payslip_type_id.id in blacklits:
                continue
            blacklits.append(record.payslip_type_id.id)
            for concept in record.payslip_type_id.concepts_ids:
                if concept.code in concepts:
                    compute = True
                    break
        return compute

    def _get_categories_search(self, total_previous, start, end):
        concepts_eval = ['IBD', 'DED_PENS', 'DED_EPS',
                         'FOND_SOL', 'FOND_SUB', 'BRTF', 'RTEFTE']
        if not self._check_concepts_belonging(concepts_eval):
            return
        param = {
            'categories': tuple(CATEGORIES_SEARCH),
            'contracts': tuple([x.contract_id.id for x in self]),
            'payslips': tuple(self.ids),
            'start': start,
            'end': end,
        }
        query = """
        SELECT HP.contract_id, HPL.category, sum(HPL.total)
        FROM hr_payslip_line as HPL
        LEFT JOIN hr_concept as HC
            ON HC.id = HPL.concept_id
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        WHERE
            HP.state = 'paid' AND
            HPL.category IN %(categories)s AND
            PP.end > %(start)s AND
            PP.start < %(end)s AND
            HP.contract_id IN %(contracts)s AND
            HPL.payslip_id NOT IN %(payslips)s AND
            COALESCE(HC.code, '') NOT IN ('PRIMA', 'PRIMA_LIQ')
        GROUP BY HP.contract_id, HPL.category
        """
        data = orm.fetchall(self._cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = {d[1]: d[2]}
            elif d[1] not in total_previous[d[0]]:
                total_previous[d[0]][d[1]] = d[2]
            else:
                total_previous[d[0]][d[1]] += d[2]

    def _get_concepts_search(self, total_concepts, start, end):
        if not self._check_concepts_belonging(CONCEPTS_SEARCH):
            return
        param = {
            'code': tuple(CONCEPTS_SEARCH),
            'contracts': tuple([x.contract_id.id for x in self]),
            'payslips': tuple(self.ids),
            'start': start,
            'end': end,
        }
        query = """
        SELECT HP.contract_id, HC.code, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        INNER JOIN hr_concept as HC
            ON HC.id = HPL.concept_id
        WHERE
            HP.state = 'paid' AND
            HC.code IN %(code)s AND
            PP.end > %(start)s AND
            PP.start < %(end)s AND
            HP.contract_id IN %(contracts)s AND
            HPL.payslip_id NOT IN %(payslips)s
        GROUP BY HP.contract_id, HC.code
        """
        data = orm.fetchall(self._cr, query, param)
        for d in data:
            if d[0] not in total_concepts:
                total_concepts[d[0]] = {d[1]: d[2]}
            elif d[1] not in total_concepts[d[0]]:
                total_concepts[d[0]][d[1]] = d[2]
            else:
                total_concepts[d[0]][d[1]] += d[2]

    def to_paid(self):
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

                neto_code = ['NETO', 'NETO_CES', 'NETO_LIQ']

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
                    analytic_distribution = record._get_distribution(
                        account, payslip_line)
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

    def to_draft(self):
        payslip_ids = [rec for rec in self if rec.state == 'paid']
        for payslip_id in payslip_ids:
            payslip_id.contract_id.remove_to_holiday_book(payslip_id)
            payslip_id.move_id.posted_before = False

        move_ids = self.with_context(
            force_delete=True).env['account.move'].browse(list(map(lambda p: p.move_id.id, payslip_ids)))
        if move_ids:
            move_ids.button_draft()
            move_ids.unlink()

        domain = [('payslip_id', 'in', [p.id for p in payslip_ids])]
        for model, parent in [('hr.leave.line', 'leave_id'), ('hr.novelty.line', 'novelty_id'), ('hr.overtime', None)]:
            lines_ids = self.env[model].search(domain)
            lines_ids.write({'state': 'validated'})

            if parent:
                parent_ids = {getattr(l, parent) for l in lines_ids}
                [p.write({'state': 'validated'}) for p in parent_ids]

        self.browse([p.id for p in payslip_ids]).write({'state': 'draft'})

    def _generate_day31_novelties(self, politics):
        """Beneficio día 31: crea las novedades estáticas de salario y de
        subsidio de transporte cuando el periodo termina el día 31 y el
        contrato tiene activo el beneficio. No duplica si ya existe una
        novedad (automática o manual) del mismo empleado, categoría y periodo."""
        self.ensure_one()
        novelties = self.env['hr.novelty']
        period = self.period_id
        contract = self.contract_id
        day31 = period.end
        if day31.day != 31 or not contract.apply_day31_benefit:
            return novelties
        if contract.date_start and contract.date_start > day31:
            return novelties
        contract_end = [d for d in (contract.date_end, contract.settlement_date) if d]
        if contract_end and min(contract_end) < day31:
            return novelties

        company = contract.company_id or self.company_id
        allowed_types = self.payslip_type_id.novelty_types_ids
        economic_variable = self.env['economic.variable'].with_company(company)
        wage = contract.get_wage(day31)['wage']

        to_create = []
        wage_type = company.day31_wage_novelty_type_id
        if wage_type and wage_type in allowed_types:
            to_create.append((wage_type, wage / 30))
        transport_type = company.day31_transport_novelty_type_id
        if transport_type and transport_type in allowed_types and \
                self._day31_has_transport_right(wage, politics, economic_variable):
            sub_trans = economic_variable.get_value_by_date('SUB_TRANS', day31)
            to_create.append((transport_type, sub_trans / 30))

        for novelty_type, amount in to_create:
            if amount <= 0 or self._day31_novelty_exists(novelty_type):
                continue
            novelty = self.env['hr.novelty'].with_company(company).create({
                'contract_id': contract.id,
                'employee_id': contract.employee_id.id,
                'novelty_type_id': novelty_type.id,
                'type_novelty': 'STATIC',
                'date_start': day31,
                'amount': amount,
                'day31_generated': True,
            })
            novelty.to_confirm()
            novelty.to_validated()
            novelties |= novelty
        return novelties

    def _day31_has_transport_right(self, wage, politics, economic_variable):
        """Reglas del subsidio de transporte evaluables antes de liquidar
        (mismas de _SUB_TRANS, salvo el tope sobre devengos del periodo)."""
        contract = self.contract_id
        fiscal_code = contract.fiscal_type_id.code
        if contract.skip_commute_allowance or fiscal_code == '12':
            return False
        if fiscal_code in ('19', '23') and \
                not politics.get('hr_payroll_co.pays_sub_trans_train_prod'):
            return False
        smmlv = economic_variable.get_value_by_date('SMMLV', self.period_id.end)
        return wage <= 2 * smmlv

    def _day31_novelty_exists(self, novelty_type):
        period = self.period_id
        return bool(self.env['hr.novelty'].search_count([
            ('employee_id', '=', self.contract_id.employee_id.id),
            ('novelty_type_id', '=', novelty_type.id),
            ('state', '!=', 'cancel'),
            '|', ('novelty_line_ids.period_id', '=', period.id),
            '&', ('date_start', '>=', period.start), ('date_start', '<=', period.end),
        ]))

    def compute_slip(self, _cr=False):
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
        global_error_log = ''
        politics = self._get_politics()
        economic_variables = {}
        total_previous = {}
        total_concepts = {}
        self._get_categories_search(
            total_previous,
            self[0].period_id.start.replace(day=1),
            self[0].period_id.end)
        self._get_concepts_search(
            total_concepts,
            self[0].period_id.start.replace(day=1),
            self[0].period_id.end)
        cr = orm.create_cursor(self._cr)
        len_self = len(self)
        value_eval = int(len_self/10) if int(len_self/10) > 0 else 1
        for i, record in enumerate(self):
            if i % value_eval == 0:
                orm.log_message(f'Calculando {i+1} de {len_self} Nóminas')
            record.error_log = ''
            record.payslip_type_id.get_sorted_concepts(sorted_concepts)
            record.payslip_type_id.get_categories_novelty(categories_novelty)
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

            # Novedades automáticas desde la pestaña Novedades del contrato
            try:
                record.contract_id.contract_novelty_ids._generate_for_payslip(
                    record)
                # Beneficio día 31
                record._generate_day31_novelties(politics)
            except ValidationError as ex:
                global_error_log += record.create_error_log(ex.__str__())
                continue

            # Novedades, Horas Extras, Ausencias
            record.compute_payslip_novelty(
                payslip_line_novelty, payslip_day_ids, data_payslip, categories_novelty)
            complement_lines = record._compute_eg_general_complement_lines(
                payslip_line_novelty, data_payslip)
            data_to_create['hr.payslip.line'] += payslip_line_novelty + \
                complement_lines

            # Dias de Nómina
            record.set_no_leave_days(payslip_day_ids)
            data_payslip['payslip_days'] = payslip_day_ids
            data_to_create['hr.payslip.day'] += payslip_day_ids

            # Conceptos de Nómina
            error_log = record.compute_payslip_line_concept(
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

    def evaluate_constraints(self):
        if self.state != 'draft':
            raise ValidationError('No está en estado borrador')
        if self.contract_id.date_start > self.period_id.end:
            raise ValidationError(
                'Le fecha de inicio del contrato es mayor a la fecha de inicio del periodo a calcular')

    def create_data_payslip(self, economic_variables, politics, total_previous, total_concepts, cr):
        c_obj = self.contract_id
        p_obj = self.period_id
        data_payslip = {
            'contract': c_obj,
            'period': p_obj,
            'payslip_type_id': self.payslip_type_id,
            # Se debe buscar el salario de este periodo
            # Tener cuidado con el diccionario que se construye
            'wage': c_obj.get_wage(p_obj.end, p_obj.start),
            'payslip_id': self.id,
            'economic_variables': economic_variables,
            'current_year_month': (self.period_id.start.year, self.period_id.start.month),
            'politics': politics,
            'payslip_processing_id': self.payslip_processing_id.id,
            TPCT: total_previous[c_obj.id] if c_obj.id in total_previous else {},
            TPCP: total_concepts[c_obj.id] if c_obj.id in total_concepts else {},
            'cr': cr,
            'cutoff_date': self.cutoff_date
        }
        return data_payslip

    def compute_payslip_novelty(self, payslip_line_novelty, payslip_day_ids, data_payslip, categories_novelty):
        pay_advance_vacation = data_payslip['politics']['hr_payroll_co.pay_advance_vacation']
        assumed_disability_february = data_payslip['politics']['hr_payroll_co.assumed_disability_february']
        domain_vac = [
            ('state', 'in', ('validated', 'paid')),
            ('contract_id', '=', self.contract_id.id),
            ('period_id.start', '>=', self.period_id.start),
            ('leave_id.category_type', 'in', ('VAC', 'VAC_MONEY'))
        ]
        domain_not_vac = [
            ('state', '=', 'validated'),
            ('period_id', '=', self.period_id.id),
            ('contract_id', '=', self.contract_id.id),
            ('leave_id.category_type', 'not in', ('VAC', 'VAC_MONEY'))
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
                                        and payslip_novelty.leave_id.category_type in ('MAT_LIC', 'PAT_LIC', 'SICKNESS')):
                                    payslip_line['qty'] += (30 -
                                                            data_payslip['period'].end.day)
                                    payslip_line['total'] += new_payslip_line['total'] * \
                                        (30 - data_payslip['period'].end.day)
                            else:
                                payslip_line['qty'] = new_payslip_line['qty']
                        else:
                            payslip_line['qty'] = new_payslip_line['qty']
                        payslip_line['total'] += new_payslip_line['total']
                        break
                if create:
                    payslip_line_novelty.append(new_payslip_line)
        for payslip_line in payslip_line_novelty:
            payslip_line['total'] = round(payslip_line['total'])
            self.update_data_payslip(data_payslip, payslip_line)
            if 'unique_key' in payslip_line:
                payslip_line.pop('unique_key')

    def _compute_eg_general_complement_lines(self, payslip_line_novelty, data_payslip):
        """Líneas de complemento empresarial para incapacidad por enfermedad general (EPS + complemento)."""
        if not data_payslip['politics'].get('hr_payroll_co.pays_eg_general_complement'):
            return []
        concept = self.env['hr.concept']
        codes = list(EG_GENERAL_TO_COMPLEMENT_CODE.keys()) + list(
            EG_GENERAL_TO_COMPLEMENT_CODE.values())
        concepts_by_code = {
            c.code: c for c in concept.search([('code', 'in', codes)])}
        eg_ids = {c.id for c in concepts_by_code.values(
        ) if c.code in EG_GENERAL_SICKNESS_CODES}
        daily_wage = data_payslip['wage'].get('wage', 0) / 30
        complement_lines = []
        for line in payslip_line_novelty:
            concept_id = line.get('concept_id')
            if not concept_id or concept_id not in eg_ids:
                continue
            leave_id = line.get('leave_id')
            if leave_id:
                leave = self.env['hr.leave'].browse(leave_id)
                if leave.amount_adjusted_to_smmlv:
                    continue
            rate = line.get('rate') or 0.0
            if rate >= 100:
                continue
            comp_rate = 100.0 - rate

            base_rec = concept.browse(concept_id)
            if not base_rec:
                continue
            base_code = base_rec.code
            comp_code = EG_GENERAL_TO_COMPLEMENT_CODE.get(base_code)
            if not comp_code:
                continue
            comp_rec = concepts_by_code.get(comp_code)
            if not comp_rec:
                continue
            qty = line.get('qty') or 1.0

            complement_total = round(daily_wage * qty * comp_rate / 100)

            payslip_line = {
                'name': comp_rec.name,
                'payslip_id': self.id,
                'category': comp_rec.category,
                'value': daily_wage,
                'qty': 1.0,
                'rate': comp_rate,
                'total': complement_total,
                'origin': 'local',
                'concept_id': comp_rec.id,
                'leave_id': line.get('leave_id'),
            }
            self.update_data_payslip(data_payslip, payslip_line)
            complement_lines.append(payslip_line)
        return complement_lines

    def set_no_leave_days(self, payslip_day_ids):
        '''
        Set days worked and days without contract
        '''
        no_worked_days = [x['day'] for x in payslip_day_ids]
        period_days = range(self.period_id.start.day,
                            self.period_id.end.day + 1)
        start_contract_in_period = self.period_id.between(
            self.contract_id.date_start)
        finish_contract_in_period = self.period_id.between(
            self.contract_id.settlement_date)

        for current_day in period_days:
            if current_day in no_worked_days:
                continue
            elif finish_contract_in_period and current_day > self.contract_id.settlement_date.day:
                payslip_day_ids.append(
                    {'payslip_id': self.id, 'day': current_day, 'day_type': 'X'})
            elif start_contract_in_period and current_day < self.contract_id.date_start.day:
                payslip_day_ids.append(
                    {'payslip_id': self.id, 'day': current_day, 'day_type': 'X'})
            else:
                payslip_day_ids.append(
                    {'payslip_id': self.id, 'day': current_day, 'day_type': 'W'})

    def compute_payslip_line_concept(self, payslip_line_concept, payslip_line_log, data_payslip, sorted_concepts):
        for concept_id in sorted_concepts[self.payslip_type_id.id]:
            # Los aportes se calculan en PILA
            if concept_id.category == 'contributions':
                continue
            if concept_id.code not in CONCEPTS:
                continue
            try:
                payslip_line = eval(
                    'concept_id._' + concept_id.code + '(data_payslip)')
                if type(payslip_line) == dict:
                    if concept_id.code == 'PRV_VAC':
                        payslip_line['total'] = payslip_line['total']
                    else:
                        payslip_line['total'] = round(payslip_line['total'])
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
                            novelty_payslip_line['total'])
                        self.update_data_payslip(
                            data_payslip, novelty_payslip_line)
                        payslip_line_concept.append(novelty_payslip_line)

            except ValidationError as ex:
                return self.create_error_log(ex.__str__())

    def update_data_payslip(self, data_payslip, payslip_line):
        if payslip_line['category'] in data_payslip:
            data_payslip[payslip_line['category']] += payslip_line['total']
        else:
            data_payslip[payslip_line['category']] = payslip_line['total']

    def build_economic_variables(self):
        current_date = self.period_id.start
        a_year_ago = current_date - relativedelta(years=1)
        periods_to_search = {
            current_date: ['SMMLV', 'SUB_TRANS', 'UVT', 'TRTEFTE', 'ANNUAL_LIMIT_25P', 'ANNUAL_LIMIT_40P',
                           'ACCAI_THRESHOLD', 'FSOL', 'FSUB'],
            a_year_ago: ['SMMLV', 'SUB_TRANS', 'TSDES']
        }

        economic_variables = self.env['economic.variable'].get_values_by_date(
            periods_to_search)
        return economic_variables

    def create_error_log(self, message):
        self.error_log = f'{self.name}: {message}\n'
        return self.error_log

    def send_mail(self):
        len_self = len(self)
        value_eval = int(len_self/10) if int(len_self/10) > 0 else 1
        mail_template = self.env.ref(MAIL_TEMPLATE)
        for i, record in enumerate(self):
            if i % value_eval == 0:
                message = f"Sendign mail from {record.name} {i+1}/{len_self}"
                orm.log_message(message)
            if record.state != 'paid':
                raise ValidationError(
                    "La nómina debe estar en estado <Pagada> para enviar el comprobante")

            if record.mail_sended:
                record.error_log = "Correo ya enviado"
            else:
                mail_template.send_mail(record.id, force_send=False)
                record.write({'mail_sended_internal': True})

    def _get_distribution(self, account, payslip_line=None):
        distribution = {}
        account = account.with_company(self.company_id) if self.company_id else account
        if account.code and account.code[0] in ('4', '5', '6', '7'):
            if self.company_id.analytic_distribution_contract:
                distribution = self.contract_id.analytic_distribution or {}
            elif self.contract_id.analytic_distribution_ids:
                for analytic in self.contract_id.analytic_distribution_ids:
                    key = analytic.analytic_account_id.id
                    if key not in distribution.keys():
                        distribution[key] = analytic.rate
                    else:
                        distribution[key] += analytic.rate
        return distribution

    def _compute_liquidation_loan(self):
        loan_ids = self.env['hr.loan'].sudo().search([
            ('state', '=', 'validated'),
            ('contract_id', '=', self.contract_id.id)
        ])
        for loan in loan_ids:
            loan.liquidate_loan(self.period_id)

    @api.model
    def default_get(self, field_list):
        res = super().default_get(field_list)
        res['location_code'] = self.env.company.chart_template
        return res
