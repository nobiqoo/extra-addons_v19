# -*- coding: utf-8 -*-
# resolucion 2388 de 2016
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.utilities_collection import orm
from odoo.addons.utilities_collection import string
from odoo.addons.utilities_collection import number
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from datetime import timedelta
from odoo.addons.utilities_collection.time import days360
from odoo.addons.hr_payroll_co.models.hr_payslip.hr_payslip import (
    EG_GENERAL_TO_COMPLEMENT_CODE,
)

import logging

_logger = logging.getLogger(__name__)

STATE = [
    ('draft', 'Borrador'),
    ('paid', 'Pagada')
]

CONTRIBUTION_LINE = {
    'tde': False, 'tae': False, 'tdp': False, 'tap': False, 'vct': False,
    'afp_to_code': None, 'eps_to_code': None, 'vct_start': None, 'vct_end': None,
    'ups': 0, 'esap_rate': 0, 'esap_cot': 0, 'men_rate': 0, 'men_cot': 0,
    'ap_vol_company': 0, 'fixes': ' ', 'ret_cont_vol': 0, 'aus_auth': None,
    'mat_auth': None, 'gd_amount': 0, 'mat_amount': 0,
}

DOCUMENT_TYPE = {
    'Pasaporte': 'PA',
    'Carné Diplomatico': 'CD',
    'Salvoconducto de Permanencia': 'SC',
    'PEP': 'PE',
    'Registro Civil': 'RC',
    'Cédula': 'CC',
    'Tarjeta de Identidad': 'TI',
    'Cédula de ciudadanía': 'CC',
    'Cédula de extranjería': 'CE',
    'Permiso por Protección Temporal': 'PT',
}


class HrContributionForm(models.Model):
    _name = 'hr.contribution.form'
    _description = 'Planilla de aportes'
    _order = 'name'

    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Selection(string='Estado', selection=STATE, default='draft')
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo',
        domain=[('active', '=', True), ('type_period', '=', 'MONTHLY')], required=True)
    contract_group_id = fields.Many2one(
        comodel_name='hr.contract.group', string='Grupo de Contrato')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)
    error_log = fields.Text(string='Errores', readonly=True)
    file_pila = fields.Binary(string='Archivo plano', readonly=True)
    file_name = fields.Char(string='Nombre archivo',
                            default='PILA.txt', readonly=True)
    branch_code = fields.Char(string='Código de sucursal')
    journal_id = fields.Many2one(
        comodel_name='account.journal', string='Diario', required=True)
    move_id = fields.Many2one(
        comodel_name='account.move', string='Asiento contable', readonly=True)

    contracts_ids = fields.Many2many(
        comodel_name='hr.contract', string='Contratos',
        relation='hr_contribution_form_hr_contract_rel',
        copy=False)
    contribution_line_ids = fields.One2many(
        comodel_name='hr.contribution.form.line', inverse_name='contribution_id',
        string='Detalle de planilla de aportes', copy=False, readonly=False)

    pens_cot_total = fields.Float(
        'Total cotización de pensión', compute='_get_totals')
    ap_vol_contributor_total = fields.Float(
        'Total aporte voluntario de pensión', compute='_get_totals')
    ap_vol_company_total = fields.Float(
        'Total aporte voluntario del aportante a pensión', compute='_get_totals')
    fsol_total = fields.Float(
        'Total aporte a fondo de solidaridad', compute='_get_totals')
    fsub_total = fields.Float(
        'Total aporte a fondo de subsistencia', compute='_get_totals')
    eps_cot_total = fields.Float('Total aporte a EPS', compute='_get_totals')
    arl_cot_total = fields.Float('Total aporte a ARL', compute='_get_totals')
    ccf_cot_total = fields.Float('Total aporte a CCF', compute='_get_totals')
    sena_cot_total = fields.Float('Total aporte a SENA', compute='_get_totals')
    icbf_cot_total = fields.Float('Total aporte a ICBF', compute='_get_totals')
    # eps_advanced_total = fields.Float('Total aporte a EPS Previas', compute='_get_totals')
    contribution_total = fields.Float('Total', compute='_get_totals')

    @api.model_create_multi
    def create(self, vals_list):
        seq_code = 'seq.hr.contribution.form'
        domain = [
            ('code', '=', seq_code),
            ('company_id', '=', self.env.company.id)
        ]
        if not self.env['ir.sequence'].search(domain):
            self.env['ir.sequence'].create({
                'name': 'Número planillas de aportes',
                'code': seq_code,
                'prefix': 'PILA-',
                'padding': 10,
                'company_id': self.env.company.id
            })
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code(seq_code) or ''
            vals['file_name'] = vals['name'] + '.txt'
        return super(HrContributionForm, self).create(vals_list)

    def unlink(self):
        contribution_remove = [x.id for x in self if x.state == 'draft']
        orm.delete(self._cr, self.env.uid,
                   'hr_contribution_form_hr_contract_rel', {'hr_contribution_form_id': contribution_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.contribution.form.line', {'contribution_id': contribution_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.contribution.form', {'id': contribution_remove})

    def load_contracts_ids(self):
        add_contract = []
        for record in self:
            param = {
                'period_id': record.period_id.id,
                'start': record.period_id.start,
                'end': record.period_id.end,
                'company_id': self.company_id.id,
            }
            if record.contract_group_id:
                filter_contract_group_id = "AND contract_group_id = %(contract_group_id)s"
                param['contract_group_id'] = record.contract_group_id.id
            else:
                filter_contract_group_id = ''
            contracts_ids_sel = """
            SELECT HC.id FROM hr_contract as HC
            LEFT JOIN (
                SELECT HCFHC.hr_contract_id AS id
                FROM hr_contribution_form_hr_contract_rel as HCFHC
                INNER JOIN hr_contribution_form HCF
                    ON HCF.id = HCFHC.hr_contribution_form_id
                WHERE
                    HCF.period_id = %(period_id)s
            ) as HCC ON HCC.id = HC.id
            WHERE
                HCC.id IS NULL AND HC.active AND HC.state in ('open', 'close') AND
                HC.date_start <= %(end)s AND 
                (HC.settlement_date IS NULL OR HC.settlement_date >= %(start)s)
                AND HC.company_id = %(company_id)s
                {fcg}
            """.format(fcg=filter_contract_group_id)
            contracts_ids = orm.fetchall(self._cr, contracts_ids_sel, param)
            for contract_id in contracts_ids:
                add_contract.append({
                    'hr_contribution_form_id': record.id,
                    'hr_contract_id': contract_id[0],
                })
        orm.create(self._cr, self.env.uid,
                   'hr_contribution_form_hr_contract_rel', add_contract, progress=True)

    def validate(self):
        for record in self:
            error_message = ''
            for contract in record.contracts_ids:
                errors = []
                partner_id = contract.employee_id.partner_id
                document_type = partner_id.l10n_latam_identification_type_id.name
                if document_type not in DOCUMENT_TYPE:
                    errors.append(
                        f'Tipo de documento de identidad invalidado para el empleado {partner_id.name}')
                if not contract.work_city_id:
                    errors.append(
                        f'El contrato {contract.name} no tiene definida la ciudad de desempeño')
                if not contract.contract_type_id:
                    errors.append(
                        f'El contrato {contract.name} no tiene definido el tipo de contrato')
                if not contract.risk_id and contract.fiscal_type_id.code != '12':
                    errors.append(
                        f'El contrato {contract.name} no tiene definido el riesgo')
                if not contract.eps_id:
                    errors.append(
                        f'El contrato {contract.name} no tiene definida la EPS')
                if not contract.ccf_id and contract.fiscal_type_id.code not in ('12', '19', '23'):
                    errors.append(
                        f'El contrato {contract.name} no tiene definida la caja de compensación')
                if not contract.arl_id:
                    errors.append(
                        f'El contrato {contract.name} no tiene definida la ARL')
                if not contract.fiscal_type_id:
                    errors.append(
                        f'El contrato {contract.name} no tiene definido el tipo de cotizante')
                if not contract.date_start:
                    errors.append(
                        f'El contrato {contract.name} no tiene definido la fecha de inicio')

                if errors:
                    error_message += '\n'.join(errors) + '\n'

            if error_message:
                raise ValidationError(error_message)

    def compute_pila(self):
        self.validate()
        contribution_line_delete = []
        contribution_line_create = []
        economic_variables = self.env['economic.variable'].get_values_by_date({
            date_ref: ['SMMLV', 'FSOL', 'FSUB', 'ACCAI_THRESHOLD']
            for date_ref in set(self.mapped('period_id').mapped('start'))
        })
        model = 'ir.config_parameter'
        politics = {
            'hr_payroll_co.eps_rate_employee': float,
            'hr_payroll_co.eps_rate_employer': float,
            'hr_payroll_co.pen_rate_employee': float,
            'hr_payroll_co.pen_rate_employer': float,
            'hr_payroll_co.pay_ccf_mat_pat': bool,
            'hr_payroll_co.apply_parafiscal_pila': bool,
            'hr_payroll_co.full_quote_february_pila': bool,
            'hr_payroll_co.pay_ccf_leave_pay': bool,
            'hr_payroll_co.dont_apply_labor_reform': bool,
            'hr_payroll_co.pay_advance_vacation': bool,
            'hr_payroll_co.pila_with_previous_ibc': bool,
            'hr_payroll_co.take_net_salary_in_pila': bool,
            'hr_payroll_co.assumed_disability_february': bool,
            'hr_payroll_co.pays_eg_general_complement': bool,
        }
        for param in politics:
            politics[param] = (politics[param])(
                self.env[model].sudo().get_param(param))
        cr = orm.create_cursor(self._cr)
        for record in self:
            if record.state != 'draft':
                continue

            record.error_log = ''
            contribution_line_delete += record.contribution_line_ids.ids
            for contract in record.contracts_ids:
                main_count = 0
                amount = 0
                main_lines = {}
                main_lines_arl = {}
                main_lines_quotation = {}
                lines_pila = []
                data = {}
                data.update(politics)
                period = {
                    'start': record.period_id.start,
                    'end': record.period_id.end,
                }
                create_line_sen_prod = False
                is_sen_line = False
                if contract.apprentice_to_worker_date and self.period_id.between(contract.apprentice_to_worker_date) \
                        and contract.apprentice_to_worker_date > self.period_id.start:
                    create_line_sen_prod = True
                    is_sen_line = True
                if create_line_sen_prod:
                    period['end'] = contract.apprentice_to_worker_date
                record.get_data(
                    data, cr, economic_variables, contract, period, lines_pila, False, is_sen_line)
                for line in lines_pila:
                    if line[1] == 'MAIN' and main_count > 0:
                        continue
                    elif line[1] == 'MAIN' and main_count == 0:
                        main_count += 1
                    amount += line[2]
                global_ibc = record.set_limits_ibc(amount, data['smmlv'])
                wage = contract.get_wage(period['end'])['wage']
                if not politics['hr_payroll_co.take_net_salary_in_pila']:
                    wage = wage if wage >= data['smmlv'] else data['smmlv']
                template_line = {
                    'contribution_id': record.id,
                    'contract_id': contract.id,
                    'global_ibc': global_ibc,
                    'afp_code': contract.afp_pension_id.afp_code if not data['retired'] else None,
                    'eps_code': contract.eps_id.eps_code or None,
                    'ccf_code': contract.ccf_id.ccf_code or None if not data['apr'] else None,
                    'arl_code': contract.arl_id.arl_code or None if not data['apr_lec'] else None,
                    'wage': wage,
                    'work_center': contract.workcenter or None,
                    'arl_risk': contract.risk_id.name or None,
                    'contract': contract,
                    'fiscal_code': data['f_type'],
                }
                if data['hr_payroll_co.apply_parafiscal_pila']:
                    template_line['exonerated'] = not global_ibc >= 10 * \
                        data['smmlv'] and not data['int'] and not data['apr']
                else:
                    template_line['exonerated'] = not data['exceeds_limit_10_smmlv'] and not data['int'] and not data['apr']
                if data['f_type'] == '23':
                    template_line['exonerated'] = True
                template_line.update(CONTRIBUTION_LINE)
                for lp in lines_pila:
                    new_line = template_line.copy()
                    record.get_indicators(lp, new_line, data, main_lines)
                    record.get_quotation(
                        lp, new_line, data, main_lines_quotation)
                    record.get_contribution_afp_eps(lp, new_line, data)
                    record.get_contribution_arl_para(
                        lp, new_line, data, main_lines_arl)
                    record.get_dates(lp, new_line, data)
                    record.round_fields(new_line)
                    contribution_line_create.append(new_line)

                if create_line_sen_prod:
                    period = {
                        'start': contract.apprentice_to_worker_date,
                        'end': record.period_id.end,
                    }
                    data_prod_line = {}
                    data_prod_line.update(politics)
                    lines_pila_prod = []
                    amount_prod = 0
                    main_count_prod = 0
                    record.get_data(
                        data_prod_line, cr, economic_variables, contract, period, lines_pila_prod, True)
                    for line in lines_pila_prod:
                        if line[1] == 'MAIN' and main_count_prod > 0:
                            continue
                        elif line[1] == 'MAIN' and main_count_prod == 0:
                            main_count_prod += 1
                        amount_prod += line[2]
                    global_ibc = record.set_limits_ibc(amount_prod, data_prod_line['smmlv'])
    
                    wage = contract.get_wage(period['end'])['wage']
                    if not politics['hr_payroll_co.take_net_salary_in_pila']:
                        wage = wage if wage >= data['smmlv'] else data['smmlv']
                    template_line_prod = {
                        'fiscal_code': data_prod_line['f_type'],
                        'contribution_id': record.id,
                        'contract_id': contract.id,
                        'global_ibc': global_ibc,
                        'afp_code': contract.afp_pension_id.afp_code if not data_prod_line['retired'] else None,
                        'eps_code': contract.eps_id.eps_code or None,
                        'ccf_code': contract.ccf_id.ccf_code or None if not data_prod_line['apr'] else None,
                        'arl_code': contract.arl_id.arl_code or None if not data_prod_line['apr_lec'] else None,
                        'wage': wage,
                        'work_center': contract.workcenter or None,
                        'arl_risk': contract.risk_id.name or None,
                        'contract': contract,
                    }

                    if data_prod_line['hr_payroll_co.apply_parafiscal_pila']:
                        template_line_prod['exonerated'] = not global_ibc >= 10 * \
                            data_prod_line['smmlv'] and not data_prod_line['int'] and not data_prod_line['apr']
                    else:
                        template_line_prod['exonerated'] = not data_prod_line['exceeds_limit_10_smmlv'] and not data_prod_line['int'] and not data_prod_line['apr']

                    template_line_prod.update(CONTRIBUTION_LINE)
                    for lp in lines_pila_prod:
                        new_line = template_line_prod.copy()
                        record.get_indicators(lp, new_line, data_prod_line, main_lines)
                        record.get_quotation(
                            lp, new_line, data_prod_line, main_lines_quotation)
                        record.get_contribution_afp_eps(lp, new_line, data_prod_line)
                        record.get_contribution_arl_para(
                            lp, new_line, data_prod_line, main_lines_arl)
                        record.get_dates(lp, new_line, data_prod_line)
                        record.round_fields(new_line)
                        contribution_line_create.append(new_line)

        orm.delete(
            self._cr, self.env.uid, 'hr.contribution.form.line', {'id': contribution_line_delete})
        orm.create(
            self._cr, self.env.uid, 'hr.contribution.form.line', contribution_line_create, progress=True)

    def get_data(self, data, cr, economic_variables, contract, period, lines_pila, is_prod_line=False, is_sen_line=False):
        """
        Construye un diccionario con la informacion necesaria
        @params:
            data: Diccionario donde se almacena la informacion
            cr: Cursor de base de datos
            economic_variables: Diccionario con las variables economiacas
            contract: Objeto hr.contract
            period: Objeto hr.period
            lines_pila: Lista vacia donde se almacenan los detalles de pila por contrato
        @return:
            None
        """
        is_liq = self.period_id.between(contract.settlement_date)
        year_month = (self.period_id.start.year, self.period_id.start.month)
        smmlv = economic_variables['SMMLV'][year_month]
        vac_money, exceeds_limit_10_smmlv, has_top40 = self.get_lines_pila(
            lines_pila, contract, cr, is_liq, smmlv, data, period, is_prod_line, is_sen_line)
        apply_labor_reform = self.env['hr.concept']._apply_labor_reform(
            {'period': self.period_id, 'politics': data})
        fiscal_code = contract.fiscal_type_id.code
        if is_prod_line:
            fiscal_code = '01'
        elif fiscal_code == '19' and not is_sen_line:
            fiscal_code = '01'
        elif fiscal_code == '12' and not is_sen_line:
            fiscal_code = '19'
        data.update({
            'cr': cr,
            'is_liq': is_liq,
            'smmlv': smmlv,
            'economic_variables': {
                'SMMLV': {year_month: smmlv},
                'FSOL': {year_month: economic_variables['FSOL'][year_month]},
                'FSUB': {year_month: economic_variables['FSUB'][year_month]},
                'ACCAI_THRESHOLD': {year_month: economic_variables['ACCAI_THRESHOLD'][year_month]},
            },
            'current_year_month': year_month,
            'vac_money': vac_money,
            'exceeds_limit_10_smmlv': exceeds_limit_10_smmlv,
            'f_type': fiscal_code,
            'f_subtype': contract.fiscal_subtype_id.code,
            'class': contract.contract_type_id.type_class,
            'apr': fiscal_code in ['19', '12', '23'],
            'apr_lec': fiscal_code == '12',
            'int': contract.contract_type_id.type_class == 'int',
            'date_start': contract.date_start,
            'settlement_date': contract.settlement_date,
            'period': self.period_id,
            'apply_ret': contract.state == 'close',
            'arl_rate': contract.risk_id.risk_percentage or 0,
            'apprentice_to_worker_date': contract.apprentice_to_worker_date,
            'is_prod_line': is_prod_line,
            'is_sen_line': is_sen_line,
            'is_transitional_regime': contract.is_transitional_regime,
            'apply_labor_reform': apply_labor_reform,
            'has_top40': has_top40,
        })
        data.update(
            {'retired': data['apr'] or data['f_subtype'] not in ['00', False]})
        param = {'contract': contract.id,
                 'start': period['start'], 'end': period['end']}
        query = """
        SELECT COUNT(HNL.amount) FROM hr_novelty_line AS HNL
        INNER JOIN hr_period AS HPP ON HPP.id = HNL.period_id
        INNER JOIN hr_novelty AS HN ON HN.id = HNL.novelty_id
        INNER JOIN hr_novelty_type AS HNT ON HNT.id = HN.novelty_type_id
        WHERE HNT.modality = 'AVP' AND HN.contract_id = %(contract)s AND apply_in_pila = 't'
        AND HPP.start BETWEEN %(start)s AND %(end)s AND HNL.state = 'paid'"""
        avp = orm._fetchall(data['cr'], query, param)
        if avp and avp[0] and avp[0][0] and not data['retired']:
            data.update({'avp': True, 'ap_vol_contributor': avp[0][0]})
        else:
            data.update({'avp': False, 'ap_vol_contributor': 0})

    def _eg_general_complement_totals_by_leave(self, cr, contract_id, period_start, period_end):
        """Suma de totales de nómina por ausencia para conceptos EG_*_COMP (complemento empresarial IEG)."""
        codes = tuple(EG_GENERAL_TO_COMPLEMENT_CODE.values())
        if not codes:
            return {}
        query = """
            SELECT
                HPL.leave_id,
                COALESCE(SUM(HPL.total), 0)
            FROM hr_payslip_line AS HPL
            INNER JOIN hr_concept AS HC ON HC.id = HPL.concept_id
            INNER JOIN hr_payslip AS HP ON HP.id = HPL.payslip_id
            INNER JOIN hr_period AS PP ON PP.id = HP.period_id
            WHERE
                HP.contract_id = %(contract)s
                AND PP.start < %(end)s AND PP.end > %(start)s
                AND HC.code IN %(codes)s
                AND HPL.leave_id IS NOT NULL
            GROUP BY HPL.leave_id
        """
        rows = orm._fetchall(cr, query, {
            'contract': contract_id,
            'start': period_start,
            'end': period_end,
            'codes': codes,
        })
        return {row[0]: row[1] for row in rows}

    def get_lines_pila(self, lines_pila, contract, cr, is_liq, smmlv, data, period, is_prod_line=False, is_sen_line=False):
        """
        Construye las lineas de la planilla
        @params:
            lines_pila: Lista vacia donde se guardan las lineas de la planilla
            contract: hr_contract
            cr: cursor de base de datos
            is_liq: bool define si el contrato tiene fecha de liquidacion en el periodo
        @return:
            int: valor correspondiente a la suma de vacaciones en dinero y liquidadas
        """
        comp_by_leave = {}
        if data.get('hr_payroll_co.pays_eg_general_complement'):
            comp_by_leave = self._eg_general_complement_totals_by_leave(
                cr, contract.id, period['start'], period['end'])
        param = {'start': period['start'],
                 'end': period['end'], 'contract': contract.id}
        hr_concept = self.env['hr.concept']
        query = """
            WITH leave_lines AS (
                SELECT
                    HL.id AS leave_id,
                    HL.leave_type_id,
                    HLL.amount,
                    HLL.date,
                    HL.date_start
                FROM
                    hr_leave_line AS HLL
                INNER JOIN hr_leave AS HL ON HLL.leave_id = HL.id
                WHERE
                    HL.contract_id = %(contract)s
                    AND HLL.date BETWEEN %(start)s AND %(end)s
            )
            SELECT
                LL.leave_id,
                HLT.category_type,
                SUM(LL.amount) AS total_amount,
                COUNT(*) FILTER (WHERE EXTRACT(DAY FROM LL.date) != 31) AS count_days,
                MIN(LL.date) AS start_date,
                MAX(LL.date) AS end_date,
                MIN(LL.date_start) AS leave_date_start,
                MAX(LL.date_start) AS leave_date_emd,
                COUNT(*) FILTER (WHERE EXTRACT(DAY FROM LL.date) != 31 OR HLT.apply_day_31) AS ibc_days
            FROM
                leave_lines AS LL
            INNER JOIN hr_leave_type AS HLT ON LL.leave_type_id = HLT.id
            GROUP BY
                LL.leave_id,
                HLT.category_type"""
        base_lines = orm._fetchall(cr, query, param)
        ibc_previous = {}
        vac_money = 0
        current_period_leave_earning = 0
        categories = ('earnings', 'o_salarial_earnings',
                      'comp_earnings', 'o_rights')
        # Construir lineas de pila
        # (leave_id, 'type', amount, days, start, end, previuos_ibc)
        for i, bl in enumerate(base_lines):
            extra_days = 0
            if period['end'].month == 2 and bl[1] in ('MAT_LIC', 'PAT_LIC', 'SICKNESS', 'AT_EP') and data['hr_payroll_co.assumed_disability_february'] == True:
                if period['end'] == bl[5]:
                    extra_days = 2 if period['end'].day == 28 else 1
                    extra_amount = 0
                    last_leave_line = self.env['hr.leave.line'].search([('leave_id', '=', bl[0]), ('date', '=', bl[5])], limit=1)
                    if last_leave_line:
                        extra_amount = last_leave_line.amount * extra_days
                    bl = list(bl)
                    bl[3] += extra_days
                    bl[2] += extra_amount
                    bl = tuple(bl)
            if bl[1] == 'VAC_MONEY':
                if period['start'] <= bl[6] <= period['end']:
                    vac_money += sum(self.env['hr.leave.line'].search([
                        ('leave_id', '=', bl[0]), ('state', '=', 'paid')]).mapped('amount'))
            elif bl[1] in ['VAC', 'NO_PAY', 'PAY']:
                posterior_vac_amount = 0
                # bl[4] = primera fecha de la ausencia dentro de este periodo;
                # bl[6] = fecha de inicio de la ausencia (date_start).
                # Con la politica activa el IBC de vacaciones se congela SIEMPRE al mes
                # anterior al inicio de las vacaciones, aunque el disfrute cruce de mes.
                if data.get('hr_payroll_co.pila_with_previous_ibc'):
                    date_ref = bl[6]
                else:
                    date_ref = bl[4] if bl[4].month > bl[6].month else bl[6]
                key = f'{date_ref.year}-{date_ref.month}'
                ibc = contract.get_ibc_previous(
                    date_ref, smmlv, exclude_vac_money=True)
                # El dia 31 no cotiza (no suma en dias) pero cuando el tipo de
                # ausencia aplica dia 31 si se paga, por lo que debe integrar el IBC.
                ibc_leave = ibc / 30 * bl[8]
                is_from_prvious_leave = False
                if data['hr_payroll_co.pay_advance_vacation']:
                    if bl[4].year > bl[6].year:
                        is_from_prvious_leave = True
                    elif bl[4].year == bl[6].year and bl[4].month > bl[6].month:
                        is_from_prvious_leave = True
                if key not in ibc_previous:
                    ibc_previous[key] = ibc / 30 * bl[3]

                if bl[1] == 'VAC':
                    posterior_vac = self.env['hr.leave.line'].search([
                        ('leave_id', '=', bl[0]), ('date', '>', period['end']), ('state', '=', 'paid')])
                    posterior_vac_amount = sum(
                        [x.amount for x in posterior_vac])
                current_period_leave_earning += bl[2]
                lines_pila.append(
                    (bl[0], bl[1], ibc_leave, bl[3], bl[4], bl[5], bl[2] + posterior_vac_amount, is_from_prvious_leave))
            else:
                comp_extra = comp_by_leave.get(bl[0], 0.0)
                line_amount = bl[2] + comp_extra
                bl_adj = list(bl)
                bl_adj[2] = line_amount
                current_period_leave_earning += line_amount
                lines_pila.append(tuple(bl_adj[:8]) + (line_amount,))
        vac_liq = {}
        hr_concept._get_total_concepts(
            cr, vac_liq, self.period_id, contract.id, ('VAC_LIQ',))
        vac_money += sum(vac_liq.values())
        first_day = contract.date_start.day if self.period_id.between(
            contract.date_start) else 1
        last_day = (contract.settlement_date.day if contract.settlement_date.day < 31 else 30) \
            if self.period_id.between(contract.settlement_date) else 30
        if contract.apprentice_to_worker_date and self.period_id.between(contract.apprentice_to_worker_date):
            apprentice_day = contract.apprentice_to_worker_date.day \
                if contract.apprentice_to_worker_date.day < 31 else 30
            if is_prod_line:
                first_day = max(first_day, apprentice_day)
            else:
                last_day = min(last_day, apprentice_day - 1)
        max_days = max(last_day - first_day + 1, 0)

        work_days = max_days - sum([x[3]for x in lines_pila])

        query = '''
            SELECT 
                COALESCE(SUM(HPL.total), 0)
            FROM hr_payslip_line AS HPL
            LEFT JOIN hr_concept AS HC
                ON HC.id = HPL.concept_id
            INNER JOIN hr_payslip AS HP
                ON HP.id = HPL.payslip_id
            INNER JOIN hr_period AS PP
                ON PP.id = HP.period_id
            WHERE 
                HP.contract_id = %(contract)s AND
                PP.start < %(end)s AND PP.end > %(start)s AND
                HPL.category IN %(categories)s AND
                (HC.code IS NULL OR HC.code NOT IN %(excludes)s) AND
                HPL.leave_id IS NULL;
            '''
        params = {
            'contract': contract.id,
            'start': period['start'],
            'end': period['end'],
            'categories': categories,
            'excludes': ('PRIMA', 'PRIMA_LIQ', 'VAC_LIQ')
        }
        earnings = orm._fetchall(cr, query, params)[0][0]
        leave_earning = current_period_leave_earning
        salary_amount = earnings + leave_earning

        tmp = {}
        hr_concept._get_total_concept_categories(
            cr, tmp, period, contract.id, categories=('o_earnings',))
        o_earnings_amount = sum(tmp.values())

        total_earnings = salary_amount + o_earnings_amount
        exceeds_limit_10_smmlv = total_earnings + vac_money >= 10 * smmlv

        has_top40 = False
        top40 = (total_earnings - leave_earning) * 0.4
        if o_earnings_amount > top40:
            amount = total_earnings - top40
            has_top40 = True
        else:
            amount = salary_amount

        if contract.contract_type_id.type_class == 'int':
            amount *= 0.7
            earnings *= 0.7
            leave_earning *= 0.7

        if amount > 25 * smmlv:
            amount = 25 * smmlv

        amount -= leave_earning

        if work_days > 0 and amount > 0:
            if data['hr_payroll_co.full_quote_february_pila'] is True and is_liq and contract.settlement_date and contract.settlement_date.month == 2:
                next_date = contract.settlement_date + relativedelta(days=1)
                if next_date.month == 3:
                    work_days += (30 - work_days)
            if is_prod_line or is_sen_line:
                date_from = self.period_id.start.replace(day=1)
                _, last_day = monthrange(date_from.year, date_from.month)
                date_to = date_from.replace(day=last_day)
                month_days = days360(date_from, date_to)
                amount_sen = (contract.wage / month_days) * work_days
                lines_pila.insert(
                    0, (None, 'MAIN', amount_sen, work_days, None, None, amount_sen))
            else:
                lines_pila.insert(
                    0, (None, 'MAIN', amount, work_days, None, None, earnings))

        if is_liq and all([x[1] != 'MAIN' for x in lines_pila]) and [x[1] != 'MAIN' for x in lines_pila]:
            last_leave = max(lines_pila, key=lambda x: x[5])
            leave_id = last_leave[0]
            type = last_leave[1]
            previous_ibc = last_leave[2]
            total_days = last_leave[3]
            start_date = last_leave[4]
            end_date = last_leave[5]
            if last_leave[1] == 'NO_PAY' and len(last_leave) == 8:
                amount = last_leave[6]
            else:
                amount = last_leave[8]

            lines_pila.remove(last_leave)
            if total_days > 1:
                leave_days = total_days - 1
                leave_previuos_ibc = previous_ibc / total_days * leave_days
                leave_amount = amount / total_days * leave_days

                main_previous_ibc = previous_ibc / total_days
                main_amount = amount / total_days
                lines_pila.insert(
                    0, (None, 'MAIN', main_previous_ibc, 1, None, None, main_amount))
                lines_pila.append((leave_id, type, leave_previuos_ibc,
                                  leave_days, start_date, end_date - timedelta(days=1), leave_amount, False))

            else:
                lines_pila.append((leave_id, 'MAIN', 0,
                                  0, start_date, end_date, 0))

        return vac_money, exceeds_limit_10_smmlv, has_top40

    def set_limits_ibc(self, ibc, smmlv):
        if ibc > 25 * smmlv:
            return 25 * smmlv
        elif ibc < smmlv:
            return smmlv
        else:
            return ibc

    def get_indicators(self, lp, new_line, data, main_lines):
        """
        Agrega a new_line los valores de los indicadores
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        ing_sen_prod = False
        ret_sen_prod = False
        if lp[1] == 'MAIN':
            key = str(new_line['contract_id']) + '-MAIN'
            if key not in main_lines.keys():
                main_lines[key] = {'is_first': True}
            if data['period'].between(data['apprentice_to_worker_date']):
                ing_sen_prod = data['is_prod_line']
                ret_sen_prod = data['is_sen_line']
        new_line['ing'] = 'X' if data['period'].between(
            data['date_start']) and 'MAIN' == lp[1] or ing_sen_prod else ' '
        new_line['leave_id'] = lp[0]
        new_line['main'] = 'MAIN' == lp[1]
        new_line['ret'] = 'X' if (
            data['apply_ret'] and data['is_liq']) or ret_sen_prod else ' '
        data['apply_ret'] = False
        new_line['vac_lr'] = 'X' if lp[1] == 'VAC' else 'L' if lp[1] == 'PAY' else ' '
        new_line['sln'] = lp[1] == 'NO_PAY'
        new_line['ige'] = lp[1] == 'SICKNESS'
        new_line['lma'] = lp[1] in ('MAT_LIC', 'PAT_LIC')
        new_line['irl'] = 0 if lp[1] != 'AT_EP' else lp[3]
        new_line['k_start'] = data['apprentice_to_worker_date'] or data['date_start'] if new_line['ing'] == 'X' else None
        # Para el retiro SENA (sin settlement_date) la fecha de retiro es el
        # ultimo dia lectivo = apprentice_to_worker_date - 1, que ademas queda
        # dentro del periodo de la planilla reportada.
        new_line['k_end'] = data['settlement_date'] or (data['apprentice_to_worker_date'] - relativedelta(days=1)) if new_line['ret'] == 'X' else None
        if new_line['main']:
            param = {'contract': new_line['contract_id'],
                     'start': data['period'].start, 'end': data['period'].end}
            query = """
            SELECT date, wage FROM wage_update_history
            where contract_id = %(contract)s AND
            date BETWEEN %(start)s AND %(end)s
            ORDER by date DESC LIMIT 1"""
            vsp = orm._fetchall(data['cr'], query, param)
            if new_line['contract'].date_start >= param['start'] and new_line['contract'].date_start <= param['end']:
                new_line['vsp'] = False
                new_line['vsp_start'] = None
            else:
                new_line['vsp'] = True if vsp else False
                new_line['vsp_start'] = vsp[0][0] if vsp else None
        else:
            new_line['vsp'] = False
            new_line['vsp_start'] = None
        new_line['vst'] = False
        if new_line['main'] and not data['apr']:
            def _is_vst_by_extra_earnings():
                extra_earnings = {}
                self.env['hr.concept']._get_total_concept_categories(
                    data['cr'], extra_earnings, data['period'], new_line['contract_id'],
                    exclude=('BASICO',), categories=('earnings', 'comp_earnings', 'o_salarial_earnings'))
                return sum(extra_earnings.values()) > 0

            def _is_vst_by_novelties():
                vst_novelty = {}
                self.env['hr.concept']._get_novelties_vst(
                    data['cr'], vst_novelty, data['period'], new_line['contract_id'])
                return sum(vst_novelty.values()) > 0 

            if data['has_top40']:
                new_line['vst'] = True
            elif _is_vst_by_extra_earnings():
                new_line['vst'] = True
            elif _is_vst_by_novelties():
                new_line['vst'] = True


        new_line['avp'] = data.get('avp', False)
        new_line['ap_vol_contributor'] = data.get('ap_vol_contributor', 0)
        new_line.pop('contract')
        if new_line['avp']:
            del data['avp'], data['ap_vol_contributor']

    def get_quotation(self, lp, new_line, data, main_lines_quotation):
        """
        Agrega a new_line los valores de los ibcs
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        ret_sen_prod = False
        if lp[1] == 'MAIN':
            key = str(new_line['contract_id']) + '-MAIN'
            if key not in main_lines_quotation.keys():
                main_lines_quotation[key] = {'is_first': True}
            ret_sen_prod = data['is_sen_line'] and data['period'].between(
                data['apprentice_to_worker_date'])

        if data['apply_labor_reform']:
            new_line['pens_days'] = lp[3] if data['f_type'] != '12' else 0
            if data['retired']:
                new_line['pens_days'] = 0
            if data['f_type'] == '19':
                new_line['pens_days'] = 0
        else:
            new_line['pens_days'] = lp[3] if not data['retired'] else 0

        new_line['eps_days'] = lp[3]
        sena_lec_dep = (
            data['f_type'] == '12' and data['f_subtype'] == '00') or ret_sen_prod

        if data['apply_labor_reform']:
            new_line['arl_days'] = lp[3]
        else:
            new_line['arl_days'] = lp[3] if not sena_lec_dep else 0

        new_line['ccf_days'] = lp[3] if not data['apr'] else 0
        new_line['w_hours'] = int(round(lp[3] * (220/30)))
        wage_type = data.get('wage_type', False)
        if wage_type:
            new_line['wage_type'] = wage_type
        else:
            if data['int']:
                new_line['wage_type'] = 'X'
            elif new_line['vst']:
                new_line['wage_type'] = 'V'
            elif data['apr']:
                new_line['wage_type'] = ' '
            else:
                new_line['wage_type'] = 'F'
            data['wage_type'] = new_line['wage_type']
        new_line['eps_ibc'] = self.set_limits_ibc(
            lp[2] if lp[1] != 'PAY' or data['int'] else lp[6], data['smmlv'] / 30 * lp[3])

        if data['f_type'] == '01' and data['f_subtype'] in ['01', '03', '06', '04', '05']:
            new_line['pens_ibc'] = 0
        elif data['apr']:
            new_line['pens_ibc'] = new_line['eps_ibc'] if data['apply_labor_reform'] and data['f_type'] != '12' else 0
            if data['f_type'] in ('19', '23'):
                new_line['pens_ibc'] = 0
        else:
            new_line['pens_ibc'] = new_line['eps_ibc']

        new_line['arl_ibc'] = 0 if data['f_type'] == '12' else new_line['eps_ibc']

        if data['f_type'] == '23':
            new_line['eps_ibc'] = 0

        if lp[1] != 'MAIN' and data['class'] == 'int':
            new_line['ccf_ibc'] = 0 if data['apr'] else (
                lp[2] + data.get('vac_money', 0))
        else:
            if lp[1] not in ['VAC', 'NO_PAY', 'PAY']:
                new_line['ccf_ibc'] = 0 if data['apr'] else (
                    lp[-1] + data.get('vac_money', 0))
            else:
                value_ibc = 0 if lp[7] is True else lp[6]
                new_line['ccf_ibc'] = 0 if data['apr'] else (
                    value_ibc + data.get('vac_money', 0))
        new_line['other_ibc'] = new_line['ccf_ibc'] if not new_line['exonerated'] else 0
        data.pop('vac_money') if 'vac_money' in data else None

    def get_contribution_afp_eps(self, lp, new_line, data):
        """
        Agrega a new_line los valores de los aportes afp y eps
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        if data['retired']:
            if data['apply_labor_reform'] and data['apr'] and not data['apr_lec']:
                if data['f_type'] == '19':
                    new_line['pens_rate'] = 0
                else:
                    new_line['pens_rate'] = (data['hr_payroll_co.pen_rate_employer'] +
                                             data['hr_payroll_co.pen_rate_employee'])/100
                new_line['fsol'] = 0
                new_line['fsub'] = 0
            else:
                new_line['pens_rate'] = 0
                new_line['fsol'] = 0
                new_line['fsub'] = 0
        elif new_line['sln']:
            new_line['pens_rate'] = data['hr_payroll_co.pen_rate_employer']/100
            new_line['fsol'] = 0
            new_line['fsub'] = 0
        else:
            hr_concept = self.env['hr.concept']
            new_line['pens_rate'] = (data['hr_payroll_co.pen_rate_employer'] +
                                     data['hr_payroll_co.pen_rate_employee'])/100

            fsol_rate = hr_concept._get_rate_from_table(
                data, 'FSOL', new_line['global_ibc'])
            fsub_rate = hr_concept._get_rate_from_table(
                data, 'FSUB', new_line['global_ibc'])

            new_line['fsol'] = new_line['pens_ibc'] * fsol_rate / 100
            new_line['fsub'] = new_line['pens_ibc'] * fsub_rate / 100

        new_line['pens_cot'] = new_line['pens_rate'] * new_line['pens_ibc']
        new_line['pens_total'] = new_line['pens_cot'] + \
            new_line['ap_vol_contributor']

        # Aplicar cálculo de reforma pensional
        self._apply_pension_reform_calculation(lp, new_line, data)

        if data['hr_payroll_co.apply_parafiscal_pila']:
            rule_eps_condition = new_line['global_ibc'] >= 10 * \
                data['smmlv'] or data['int'] or data['apr']
        else:
            rule_eps_condition = data['exceeds_limit_10_smmlv'] or data['int'] or data['apr']

        if rule_eps_condition:
            new_line['eps_rate'] = (data['hr_payroll_co.eps_rate_employer'] +
                                    data['hr_payroll_co.eps_rate_employee'])/100
        elif new_line['sln']:
            new_line['eps_rate'] = 0
        else:
            new_line['eps_rate'] = data['hr_payroll_co.eps_rate_employee'] / 100
        new_line['eps_cot'] = new_line['eps_rate'] * new_line['eps_ibc']

    def get_contribution_arl_para(self, lp, new_line, data, main_lines_arl):
        """
        Agrega a new_line los valores de los aportes arl y parafiscales
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        ret_sen_prod = False
        if lp[1] == 'MAIN':
            key = str(new_line['contract_id']) + '-MAIN'
            if key not in main_lines_arl.keys():
                main_lines_arl[key] = {'is_first': True}
                ret_sen_prod = True if data['period'].between(
                    data['apprentice_to_worker_date']) else False

        pay_arl = new_line['main'] and not data['f_type'] == '12'

        new_line['arl_rate'] = data['arl_rate'] / 100 if pay_arl else 0
        new_line['arl_cot'] = new_line['arl_rate'] * new_line['arl_ibc']

        if lp[1] in ['VAC', 'NO_PAY', 'PAY'] and lp[7] == True:
            new_line['ccf_rate'] = 0
        else:
            pay_ccf = new_line['main']
            pay_ccf |= data['hr_payroll_co.pay_ccf_mat_pat'] and new_line['lma']
            pay_ccf |= data['hr_payroll_co.pay_ccf_leave_pay'] and lp[1] == 'PAY'
            pay_ccf |= lp[1] == 'VAC'
            pay_ccf |= not new_line['main'] and (new_line['ret'] == 'X')
            pay_ccf &= not data['apr']
            new_line['ccf_rate'] = 0.04 if pay_ccf else 0
        new_line['ccf_cot'] = new_line['ccf_ibc'] * new_line['ccf_rate']

        if data['hr_payroll_co.apply_parafiscal_pila']:
            pay_sena = new_line['global_ibc'] >= 10 * data['smmlv']
        else:
            pay_sena = data['exceeds_limit_10_smmlv']
        pay_sena |= data['int']
        pay_sena &= not new_line['sln']
        new_line['sena_rate'], new_line['icbf_rate'] = (
            0.02, 0.03) if pay_sena else (0, 0)
        new_line['sena_cot'] = new_line['other_ibc'] * new_line['sena_rate']
        new_line['icbf_cot'] = new_line['other_ibc'] * new_line['icbf_rate']

    def get_dates(self, lp, new_line, data):
        """
        Agrega a new_line los valores de las fechas
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        date_fields = ['sln_start', 'sln_end', 'ige_start', 'ige_end',
                       'lma_start', 'lma_end', 'vac_start', 'vac_end', 'atep_start', 'atep_end']
        for df in date_fields:
            leave, date = df.split('_')
            date = lp[4] if date == 'start' else lp[5]
            set_date = leave == 'sln' and lp[1] == 'NO_PAY'
            set_date |= leave == 'ige' and lp[1] == 'SICKNESS'
            set_date |= leave == 'lma' and lp[1] in ('MAT_LIC', 'PAT_LIC')
            set_date |= leave == 'vac' and lp[1] in ('VAC', 'PAY')
            set_date |= leave == 'atep' and lp[1] == 'AT_EP'
            new_line[df] = date if set_date else None

    def round_fields(self, new_line):
        rp1 = ['pens_ibc', 'eps_ibc', 'arl_ibc', 'ccf_ibc', 'other_ibc']
        rp = ['pens_cot', 'ap_vol_contributor', 'pens_total', 'fsol', 'fsub',
              'eps_cot', 'arl_cot', 'ccf_cot', 'sena_cot', 'icbf_cot',
              'pens_public', 'pens_accai']
        for r in rp1:
            new_line[r] = number.rp1(new_line[r])
        for r in rp:
            new_line[r] = number.rp(new_line[r])

    def set_file_pila(self):
        for record in self:
            body = record.build_file()
            body = string.remove_accents(body)
            body = string.bytes2base64(body)
            record.write({'file_pila': body})

    def build_file(self):
        total_text = ''
        break_line = '\r\n'
        # ----- HEADER ----- #
        hl = [''] * (22 + 1)
        # 1: Tipo de registro
        hl[1] = '01'

        # 2: Modalidad de la planilla
        hl[2] = '1'

        # 3: Secuencia # TODO Está generando el 0001 pero se debe validar que siempre sea el mismo
        hl[3] = '0001'

        # 4: Nombre o razon social del aportante
        hl[4] = string.prep_field(self.company_id.partner_id.name, size=200)

        # 5: Tipo de documento del aportante # TODO Asignado directamente tipo de documento NIT
        hl[5] = 'NI'

        # 6: Numero de identificacion del aportante
        hl[6] = string.prep_field(self.company_id.partner_id.vat, size=16)

        # 7: Digito de verificacion
        hl[7] = str(self.company_id.partner_id.l10n_co_verification_code)

        # 8: Tipo de planilla
        hl[8] = 'E'

        # 9: Numero de la planilla asociada a esta planilla # TODO revisar casos de planillas N y F
        hl[9] = string.prep_field(" ", size=10)

        # 10: Fecha de planilla de pago asociada a esta planilla
        hl[10] = string.prep_field(" ", size=10)

        # 11: Forma de presentacion # TODO temporalmente forma de presentacion unica
        hl[11] = string.prep_field('U', size=1)

        # 12: Codigo de sucursal # TODO referente campo 11
        hl[12] = string.prep_field(self.branch_code, size=10)

        # 13: Nombre de la sucursal
        hl[13] = string.prep_field(self.branch_code, size=40)

        # 14: Código de la ARL a la cual el aportante se encuentra afiliado

        hl[14] = string.prep_field(self.company_id.arl_id.arl_code, size=6)

        # 15: Período de pago para los sistemas diferentes al de salud
        hl[15] = string.prep_field(self.period_id.start, size=7)

        # 16: Período de pago para el sistema de salud.
        hl[16] = string.prep_field(
            self.period_id.start + relativedelta(months=1), size=7)

        # 17: Número de radicación o de la Planilla Integrada de Liquidación de Aportes. (Asignado por el sistema)
        hl[17] = string.prep_field(" ", size=10)

        # 18: Fecha de pago (aaaa-mm-dd) (Asignado por el siustema)
        hl[18] = string.prep_field(" ", size=10)

        # 19: Numero total de empleados
        hl[19] = string.prep_field(len(self.contracts_ids),
                                   align='right', fill='0', size=5)

        # 20: Valor total de la nomina
        ibp_sum = sum([x.ccf_ibc for x in self.contribution_line_ids])
        hl[20] = string.prep_field(
            int(ibp_sum), align='right', fill='0', size=12)

        # 21: Tipo de aportante
        hl[21] = string.prep_field("1", size=2)

        # 22: Codigo de operador de informacion
        hl[22] = string.prep_field(" ", size=2)

        for x in hl:
            total_text += x
        total_text += break_line

        # ----- BODY ----- #
        i, j = 0, len(self.contribution_line_ids)
        seq = 0
        main_lines = {}
        for l in self.contribution_line_ids:
            seq += 1
            employee = l.contract_id.employee_id
            document_type = DOCUMENT_TYPE.get(
                employee.partner_id.l10n_latam_identification_type_id.name)

            ret_sen_prod = False
            if l.main:
                key = str(l.contract_id.id) + '-MAIN'
                if key not in main_lines.keys():
                    main_lines[key] = {'is_first': True}
                    ret_sen_prod = True if self.period_id.between(
                        l.contract_id.apprentice_to_worker_date) else False

            fiscal_type_code = string.prep_field(l.fiscal_code if l.fiscal_code != '51' else '01',
                                                     size=2)

            bl = [''] * (98 + 1)
            # 1: Tipo de registro
            bl[1] = '02'
            # 2: Secuencia
            bl[2] = string.prep_field(seq, align='right', fill='0', size=5)
            # 3: Tipo de documento de cotizante
            bl[3] = string.prep_field(document_type, size=2)
            # 4: Numero de identificacion cotizante
            bl[4] = string.prep_field(employee.partner_id.vat, size=16)
            # 5: Tipo de cotizante
            bl[5] = fiscal_type_code
            # 6: Subtipo de cotizante
            bl[6] = string.prep_field(
                l.contract_id.fiscal_subtype_id.code or '00', size=2)
            # 7: Extranjero no obligado a cotizar pensiones
            foreign = False
            # foreign = employee.partner_id.country_id.code != 'CO' and document_type in ('CE', 'PA', 'CD')
            bl[7] = 'X' if foreign else ' '
            # 8: Colombiano en el exterior
            is_col = True if document_type in (
                'CC', 'TI') and employee.partner_id.country_id.code == 'CO' else False
            in_ext = False
            if l.contract_id.work_city_id:
                in_ext = True if l.contract_id.work_city_id.state_id.country_id.code != 'CO' else False
            bl[8] = 'X' if is_col and in_ext else ' '
            # 9: Código del departamento de la ubicación laboral
            bl[9] = string.prep_field(
                l.contract_id.work_city_id.state_id.dian_code, size=2)
            # 10: Código del municipio de ubicación laboral
            bl[10] = string.prep_field(
                l.contract_id.work_city_id.dian_code[2:], size=3)
            # 11: Primer apellido
            if employee.partner_id.lastname1:
                pap = string.unicode_remove_accents(
                    employee.partner_id.lastname1)
                bl[11] = string.prep_field(pap, size=20)
            else:
                bl[11] = string.prep_field(' ', size=20)
            # 12: Segundo apellido
            if employee.partner_id.lastname2:
                sap = string.unicode_remove_accents(
                    employee.partner_id.lastname2)
                bl[12] = string.prep_field(sap, size=30)
            else:
                bl[12] = string.prep_field(' ', size=30)
            # 13: Primer nombre
            if employee.partner_id.name1:
                pno = string.unicode_remove_accents(employee.partner_id.name1)
                bl[13] = string.prep_field(pno, size=20)
            else:
                bl[13] = string.prep_field(' ', size=20)
            # 14: Segundo nombre
            if employee.partner_id.name2:
                sno = string.unicode_remove_accents(employee.partner_id.name2)
                bl[14] = string.prep_field(sno, size=30)
            else:
                bl[14] = string.prep_field(' ', size=30)
            # 15: Ingreso
            bl[15] = l.ing or ' '
            # 16: Retiro
            bl[16] = l.ret or ' '
            # 17: Traslasdo desde otra eps
            bl[17] = 'X' if l.tde else ' '
            # 18: Traslasdo a otra eps
            bl[18] = 'X' if l.tae else ' '
            # 19: Traslasdo desde otra administradora de pensiones
            bl[19] = 'X' if l.tdp else ' '
            # 20: Traslasdo a otra administradora de pensiones
            bl[20] = 'X' if l.tap else ' '
            # 21: Variacion permanente del salario
            bl[21] = 'X' if l.vsp else ' '
            # 22: Correcciones
            bl[22] = l.fixes or ' '
            # 23: Variacion transitoria del salario
            bl[23] = 'X' if l.vst else ' '
            # 24: Suspension temporal del contrato
            bl[24] = 'X' if l.sln else ' '
            # 25: Incapacidad temporal por enfermedad general
            bl[25] = 'X' if l.ige else ' '
            # 26: Licencia de maternidad o paternidad
            bl[26] = 'X' if l.lma else ' '
            # 27: Vacaciones, licencia remunerada
            bl[27] = l.vac_lr if l.vac_lr else ' '
            # 28: Aporte voluntario
            bl[28] = 'X' if l.avp else ' '
            # 29: Variacion de centro de trabajo
            bl[29] = 'X' if l.vct else ' '
            # 30: Dias de incapacidad por enfermedad laboral
            bl[30] = string.prep_field("{:02.0f}".format(
                l.irl), align='right', fill='0', size=2)
            # 31: Codigo de la administradora de fondos de pensiones
            bl[31] = string.prep_field(l.afp_code, size=6)
            # 32: Codigo de administradora de pensiones a la cual se traslada el afiliado #TODO
            bl[32] = string.prep_field(l.afp_to_code, size=6)
            # 33: Codigo de EPS a la cual pertenece el afiliado
            bl[33] = string.prep_field(l.eps_code or l.contract_id.eps_id.eps_code, size=6)
            # 34: Codigo de eps a la cual se traslada el afiliado
            bl[34] = string.prep_field(l.eps_to_code, size=6)
            # 35: Código CCF a la cual pertenece el afiliado
            bl[35] = string.prep_field(l.ccf_code, size=6)
            # 36: Numero de dias cotizados a pension
            bl[36] = string.prep_field("{:02.0f}".format(
                l.pens_days), align='right', fill='0', size=2)
            # 37: Numero de dias cotizados a salud
            bl[37] = string.prep_field("{:02.0f}".format(
                l.eps_days), align='right', fill='0', size=2)
            # 38: Numero de dias cotizados a ARL
            bl[38] = string.prep_field("{:02.0f}".format(
                l.arl_days), align='right', fill='0', size=2)
            # 39: Numero de dias cotizados a CCF
            bl[39] = string.prep_field("{:02.0f}".format(
                l.ccf_days), align='right', fill='0', size=2)
            # 40: Salario basico
            bl[40] = string.prep_field("{:09.0f}".format(
                l.wage), align='right', fill='0', size=9)
            # 41: Salario integral, resolucion 454
            bl[41] = l.wage_type
            # 42: IBC pension
            bl[42] = string.prep_field("{:09.0f}".format(
                l.pens_ibc), align='right', fill='0', size=9)
            # 43: IBC salud
            bl[43] = string.prep_field("{:09.0f}".format(
                l.eps_ibc), align='right', fill='0', size=9)
            # 44: IBC arl
            bl[44] = string.prep_field("{:09.0f}".format(
                l.arl_ibc), align='right', fill='0', size=9)
            # 45: IBC CCF
            bl[45] = string.prep_field("{:09.0f}".format(
                l.ccf_ibc), align='right', fill='0', size=9)
            # 46: Tarifa de aporte a pensiones
            bl[46] = string.prep_field("{:01.5f}".format(
                l.pens_rate), align='right', fill='0', size=7)
            # 47: Cotizacion pension
            bl[47] = string.prep_field("{:09.0f}".format(
                l.pens_cot), align='right', fill='0', size=9)
            # 48: Aportes voluntarios del afiliado
            bl[48] = string.prep_field("{:09.0f}".format(
                l.ap_vol_contributor), align='right', fill='0', size=9)
            # 49: Aportes voluntarios del aportante
            bl[49] = string.prep_field("{:09.0f}".format(
                l.ap_vol_company), align='right', fill='0', size=9)
            # 50: Total cotizacion pensiones
            bl[50] = string.prep_field("{:09.0f}".format(
                l.pens_total), align='right', fill='0', size=9)
            # 51: Aportes a fondo solidaridad
            bl[51] = string.prep_field("{:09.0f}".format(
                l.fsol), align='right', fill='0', size=9)
            # 52: Aportes a fondo subsistencia
            bl[52] = string.prep_field("{:09.0f}".format(
                l.fsub), align='right', fill='0', size=9)
            # 53: Valor no retenido por aportes voluntarios
            bl[53] = string.prep_field("{:09.0f}".format(
                l.ret_cont_vol), align='right', fill='0', size=9)
            # 54: Tarifa de aportes salud
            bl[54] = string.prep_field("{:01.5f}".format(
                l.eps_rate), align='right', fill='0', size=7)
            # 55: Aportes salud
            bl[55] = string.prep_field("{:09.0f}".format(
                l.eps_cot), align='right', fill='0', size=9)
            # 56: Total UPS adicional
            bl[56] = string.prep_field("{:09.0f}".format(
                l.ups), align='right', fill='0', size=9)
            # 57: Numero de autorizacion de incapacidad
            bl[57] = string.prep_field(l.aus_auth, size=15)
            # 58: Valor de la incapacidad por enf general
            bl[58] = string.prep_field("{:09.0f}".format(
                l.gd_amount), align='right', fill='0', size=9)
            # 59: Numero de autorizacion por licencia de maternidad
            bl[59] = string.prep_field(l.mat_auth, size=15)
            # 60: Valor de licencia de maternidad
            bl[60] = string.prep_field("{:09.0f}".format(
                l.mat_amount), align='right', fill='0', size=9)
            # 61: Tarifa de aportes a riesgos laborales
            bl[61] = string.prep_field("{:01.5f}".format(
                l.arl_rate), align='right', fill='0', size=9)
            # 62: Centro de trabajo
            bl[62] = string.prep_field(
                l.work_center, align='right', fill='0', size=9)
            # 63: Cotizacion obligatoria a riesgos laborales
            bl[63] = string.prep_field("{:09.0f}".format(
                l.arl_cot), align='right', fill='0', size=9)
            # 64: Tarifa de aportes CCF
            bl[64] = string.prep_field("{:01.5f}".format(
                l.ccf_rate), align='right', fill='0', size=7)
            # 65: Aportes CCF
            bl[65] = string.prep_field("{:09.0f}".format(
                l.ccf_cot), align='right', fill='0', size=9)
            # 66: Tarifa SENA
            bl[66] = string.prep_field("{:01.5f}".format(
                l.sena_rate), align='right', fill='0', size=7)
            # 67: Aportes SENA
            bl[67] = string.prep_field("{:09.0f}".format(
                l.sena_cot), align='right', fill='0', size=9)
            # 68: Tarifa ICBF
            bl[68] = string.prep_field("{:01.5f}".format(
                l.icbf_rate), align='right', fill='0', size=7)
            # 69: Aportes ICBF
            bl[69] = string.prep_field("{:09.0f}".format(
                l.icbf_cot), align='right', fill='0', size=9)
            # 70: Tarifa ESAP
            bl[70] = string.prep_field("{:01.5f}".format(
                l.esap_rate), align='right', fill='0', size=7)
            # 71: Aportes ESAP
            bl[71] = string.prep_field("{:09.0f}".format(
                l.esap_cot), align='right', fill='0', size=9)
            # 72: Tarifa MEN
            bl[72] = string.prep_field("{:01.5f}".format(
                l.men_rate), align='right', fill='0', size=7)
            # 73: Aportes MEN
            bl[73] = string.prep_field("{:09.0f}".format(
                l.men_cot), align='right', fill='0', size=9)
            # 74: Tipo de documento del cotizante principal
            bl[74] = string.prep_field(' ', size=2)
            # 75: Numero de documento de cotizante principal
            bl[75] = string.prep_field(' ', size=16)
            # 76: Exonerado de aportes a paraficales y salud
            bl[76] = 'S' if l.exonerated else 'N'
            # 77: Codigo de la administradora de riesgos laborales
            bl[77] = string.prep_field(l.arl_code, size=6)
            # 78: Clase de riesgo en la cual se encuentra el afiliado
            bl[78] = string.prep_field(l.arl_risk, size=1)
            # 79: Indicador de tarifa especial de pensiones
            bl[79] = string.prep_field(' ', size=1)
            # 80: Fecha de ingreso
            bl[80] = string.prep_field(l.k_start, size=10)
            # 81: Fecha de retiro
            bl[81] = string.prep_field(l.k_end, size=10)
            # 82: Fecha de inicio de VSP
            bl[82] = string.prep_field(l.vsp_start, size=10)
            # 83: Fecha de inicio SLN
            bl[83] = string.prep_field(l.sln_start, size=10)
            # 84: Fecha de fin SLN
            bl[84] = string.prep_field(l.sln_end, size=10)
            # 85: Fecha de inicio IGE
            bl[85] = string.prep_field(l.ige_start, size=10)
            # 86: Fecha de fin IGE
            bl[86] = string.prep_field(l.ige_end, size=10)
            # 87: Fecha de inicio LMA
            bl[87] = string.prep_field(l.lma_start, size=10)
            # 88: Fecha de fin LMA
            bl[88] = string.prep_field(l.lma_end, size=10)
            # 89: Fecha de inicio VAC
            bl[89] = string.prep_field(l.vac_start, size=10)
            # 90: Fecha de fin VAC
            bl[90] = string.prep_field(l.vac_end, size=10)

            bl[91] = string.prep_field(l.vct_start, size=10)
            bl[92] = string.prep_field(l.vct_end, size=10)
            # 93: Fecha de inicio ATEP
            bl[93] = string.prep_field(l.atep_start, size=10)
            # 94: Fecha de fin ATEP
            bl[94] = string.prep_field(l.atep_end, size=10)
            # 95: IBC otros parafiscales
            bl[95] = string.prep_field("{:09.0f}".format(
                l.other_ibc), align='right', fill='0', size=9)

            # 96: Numero de horas laboradas
            bl[96] = string.prep_field("{:03.0f}".format(
                l.w_hours), align='right', fill='0', size=3)

            bl[97] = string.prep_field('', size=10)

            # 98: riesgo laboral
            # ((1|2|3|4|5)(d[4])(01|02))
            company_partner = self.env.company.partner_id

            if not l.contract_id.risk_id.name and fiscal_type_code != '12':
                raise ValidationError(
                    f'El contrato {l.contract_id.name} no tiene el riesgo laboral configurado')
            if not company_partner.classification_id.code:
                raise ValidationError(
                    f'La compañia {company_partner.name} no tiene configurado el CIIU')
            if not company_partner.economic_subactivity:
                raise ValidationError(
                    f'La compañia {company_partner.name} no tiene subactividad económica')

            if fiscal_type_code != '12':
                partner = l.contract_id.employee_id.partner_id
                economic_activity_code = ''.join([
                    l.contract_id.risk_id.name,
                    partner.classification_id.code if partner.classification_id else company_partner.classification_id.code,
                    partner.economic_subactivity if partner.economic_subactivity else company_partner.economic_subactivity
                ])
            else:
                economic_activity_code = '0000000'
            bl[98] = string.prep_field(economic_activity_code, size=7)

            i += 1
            c=0
            cname = []
            for x in bl:
                if (11 <= c <= 14) and isinstance(x, str):
                    cname.append(x.strip())
                if x == False:
                    _logger.error('hr_contribution_form/build_file PILA')
                    _logger.info('posición %s' % c)
                    _logger.info('resultado %s' % x)
                    _logger.info(' '.join(cname))
                total_text += x
                c += 1
            total_text += break_line

        return total_text

    def to_paid(self):
        ap_concepts = {}
        codes_ap = [
            'AP_PENS', 'AP_EPS', 'AP_ARL', 'AP_CCF', 'AP_SENA', 'AP_ICBF']
        self.get_contributions_concepts(ap_concepts, codes_ap)
        new_move_line = []
        move_ids = []

        economic_variables = self.env['economic.variable'].get_values_by_date({
            date: ['SMMLV', 'ACCAI_THRESHOLD']
            for date in set(self.mapped('period_id').mapped('start'))
        })

        politics = {
            'hr_payroll_co.pen_rate_employee': float,
            'hr_payroll_co.pen_rate_employer': float,
        }
        for param in politics:
            politics[param] = (politics[param])(
                self.env['ir.config_parameter'].sudo().get_param(param))

        for record in self:
            if not record.contribution_line_ids:
                raise ValidationError(
                    'No se puede causar una planilla sin registros por procesar')
            record.error_log = ''
            account_move = {
                'date': record.period_id.end,
                'currency_id': record.company_id.currency_id.id,
                'journal_id': record.journal_id.id,
                'move_type': 'entry',
                'state': 'draft',
            }
            move_id = self.env['account.move'].create(account_move)
            move_ids.append(move_id.id)
            record.write({'move_id': move_id.id, 'state': 'paid'})
            contributions = record.get_sum_contribution_line()
            deductions = record.get_sum_deduction_line(
                tuple([x[0] for x in contributions]))
            qty_ap = 6  # [pens, eps, arl, ccf, sena, icbf]
            for con in contributions:
                contract = self.env['hr.contract'].browse(con[0])
                contract_type = contract.contract_type_id
                prefix_account = f'{contract_type.type_class}_{contract_type.section}_'
                for i in range(qty_ap):
                    amount = con[i + 1] - deductions.get(con[0], [0]*qty_ap)[i]
                    if amount <= 0:
                        continue
                    concept = ap_concepts[codes_ap[i]]
                    if concept.code == 'AP_EPS':
                        prv_eps_cot = self.get_cot_eps_previous(contract.id)
                        if prv_eps_cot:
                            amount = abs(amount - prv_eps_cot)

                    if concept.code == 'AP_PENS':
                        apply_pension_reform = concept._apply_pension_reform(
                            {'period': record.period_id})
                        if not apply_pension_reform or contract.is_transitional_regime:
                            # Régimen tradicional
                            debit_line, credit_line = self._create_move_lines_for_concept(
                                move_id.id, concept, prefix_account, amount, contract)
                            new_move_line.extend([debit_line, credit_line])
                        else:
                            # Reforma de pensiones
                            ap_pens_concepts = {}
                            self.get_contributions_concepts(
                                ap_pens_concepts, ['AP_PENS_PUBLIC', 'AP_PENS_ACCAI'])

                            pension_lines = self._handle_pension_reform(
                                record, move_id.id, amount, contract, prefix_account,
                                ap_pens_concepts, economic_variables, politics)
                            new_move_line.extend(pension_lines)
                    else:
                        # Otros conceptos
                        debit_line, credit_line = self._create_move_lines_for_concept(
                            move_id.id, concept, prefix_account, amount, contract)
                        new_move_line.extend([debit_line, credit_line])

        self.env['account.move.line'].create(new_move_line)
        self.env['account.move'].browse(move_ids).action_post()

    def get_contributions_concepts(self, ap_concepts, codes_ap):
        hr_concep = self.env['hr.concept']
        for code in codes_ap:
            concept = hr_concep.search([('code', '=', code)])
            if not concept:
                raise ValidationError(
                    f'El concepto de nómina con código {code} no se encontró')
            elif len(concept) > 1:
                raise ValidationError(
                    f'Se hallaron {len(concept)} conceptos de nómina con código {code}')
            ap_concepts[code] = concept

    def get_sum_contribution_line(self):
        param = {'contribution': self.id, }
        query = """
        SELECT 
            contract_id,
            COALESCE(SUM(pens_total),0)+COALESCE(SUM(fsol),0)+COALESCE(SUM(fsub),0)-COALESCE(SUM(ap_vol_contributor),0)-COALESCE(SUM(ap_vol_company),0),
            COALESCE(SUM(eps_cot),0),
            COALESCE(SUM(arl_cot),0),
            COALESCE(SUM(ccf_cot),0),
            COALESCE(SUM(sena_cot),0),
            COALESCE(SUM(icbf_cot),0)
        FROM hr_contribution_form_line
        WHERE contribution_id = %(contribution)s
        GROUP BY contract_id
        """
        res = orm.fetchall(self._cr, query, param)
        return res

    def get_sum_deduction_line(self, contract_ids):
        """
        Consulta las lineas de nomina y agrupa por contrato
        @params:
            contract_ids: Tupla con ids de contratos
        @return:
            dict -> key = contract_id, value = [pens, eps, arl, ccf, sena, icbf]
        """
        res = {}
        codes = ('DED_PENS', 'FOND_SOL', 'FOND_SUB', 'DED_EPS',
                 'DED_PENS_PUBLIC', 'DED_PENS_ACCAI')
        param = {
            'codes': codes,
            'start': self.period_id.start,
            'end': self.period_id.end,
            'contracts': contract_ids,
        }
        query = """
        SELECT HP.contract_id, HC.code, COALESCE(SUM(HPL.total),0)
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
            HP.contract_id IN %(contracts)s AND
            HC.code in %(codes)s
        GROUP BY HP.contract_id, HC.code
        """
        data = orm.fetchall(self._cr, query, param)
        for d in data:
            i = 1 if d[1] == 'DED_EPS' else 0
            if d[0] not in res:
                res[d[0]] = [0] * 6
            res[d[0]][i] += d[2]
        return res

    def to_draft(self):
        contribution_ids = []
        move_ids = []
        for record in self:
            if record.state != 'paid':
                continue
            contribution_ids.append(record.id)
            move_ids.append(record.move_id.id)
            record.move_id.posted_before = False
        self.browse(contribution_ids).write({'state': 'draft'})
        moves = self.env['account.move'].browse(move_ids)
        moves.button_draft()
        moves.unlink()

    def _get_totals(self):
        for pila in self:
            pens_cot = 0
            ap_vol_contributor = 0
            ap_vol_company = 0
            fsol = 0
            fsub = 0
            eps_cot = 0
            arl_cot = 0
            ccf_cot = 0
            sena_cot = 0
            icbf_cot = 0

            for line in pila.contribution_line_ids:
                pens_cot += line.pens_cot
                ap_vol_contributor += line.ap_vol_contributor
                ap_vol_company += line.ap_vol_company
                fsol += line.fsol
                fsub += line.fsub
                eps_cot += line.eps_cot
                arl_cot += line.arl_cot
                ccf_cot += line.ccf_cot
                sena_cot += line.sena_cot
                icbf_cot += line.icbf_cot

            pila.pens_cot_total = pens_cot
            pila.ap_vol_contributor_total = ap_vol_contributor
            pila.ap_vol_company_total = ap_vol_company
            pila.fsol_total = fsol
            pila.fsub_total = fsub
            pila.eps_cot_total = eps_cot
            pila.arl_cot_total = arl_cot
            pila.ccf_cot_total = ccf_cot
            pila.sena_cot_total = sena_cot
            pila.icbf_cot_total = icbf_cot
            pila.contribution_total = sum(
                [pens_cot, ap_vol_contributor, ap_vol_company, fsol, fsub, eps_cot, arl_cot, ccf_cot, sena_cot, icbf_cot])

    def _get_distribution(self, contract, account):
        distribution = {}
        account = account.with_company(self.company_id) if self.company_id else account
        if account.code and account.code[0] in ('4', '5', '6', '7'):
            if self.company_id.analytic_distribution_contract:
                distribution = contract.analytic_distribution
            elif contract.analytic_distribution_ids:
                for analytic in contract.analytic_distribution_ids:
                    key = analytic.analytic_account_id.id
                    if key not in distribution.keys():
                        distribution[key] = analytic.rate
                    else:
                        distribution[key] += analytic.rate
        return distribution

    def get_cot_eps_previous(self, contract):
        eps_advanced_total = 0
        # Solo hay EPS anticipada si las vacaciones se pagan por adelantado; de lo
        # contrario cada dia de disfrute se descuenta en la nomina de su periodo.
        if not self.env['ir.config_parameter'].sudo().get_param('hr_payroll_co.pay_advance_vacation'):
            return eps_advanced_total
        for line in self.contribution_line_ids.filtered(lambda x: x.leave_id and x.leave_id.leave_type_id.category_type == 'VAC' and x.contract_id.id == contract):
            if line.leave_id.date_start < self.period_id.start:
                total_previous = {}
                previous_pila_value = 0
                lines_previous = line.leave_id.leave_line_ids.filtered(
                    lambda x: x.date < self.period_id.start)
                periods = list(set([x.period_id for x in lines_previous]))
                for period in periods:
                    self.env['hr.concept']._get_total_concepts(
                        self._cr, total_previous, {'start': period.start, 'end': period.end}, line.contract_id.id, ('DED_EPS',))
                    previous_pila = self.env['hr.contribution.form.line'].search([
                        ('contract_id', '=', line.contract_id.id),
                        ('contribution_id.state', '=', 'paid'),
                        ('contribution_id.period_id', '=', period.id)
                    ])
                    previous_pila_value += sum(
                        [x.eps_cot for x in previous_pila])
                eps_advanced_total += sum(total_previous.values()
                                          ) - previous_pila_value
        return eps_advanced_total

    def _apply_pension_reform_calculation(self, lp, new_line, data):
        """
        Aplica el cálculo de la reforma pensional dividiendo entre público y ACCAI
        @params:
            lp: Tupla de línea de planilla
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con información relevante
        """
        new_line['pens_public'] = 0
        new_line['pens_accai'] = 0

        # Verificar si aplica reforma pensional
        if not self.env['hr.concept']._apply_pension_reform({'period': self.period_id}):
            return

        # Si es régimen transicional, no aplica división
        if data.get('is_transitional_regime', False):
            return

        # Calcular umbral ACCAI proporcional a los dias de la linea
        year_month = (self.period_id.start.year, self.period_id.start.month)
        smmlv = data['economic_variables']['SMMLV'][year_month]
        accai_threshold = data['economic_variables']['ACCAI_THRESHOLD'][year_month]
        days = lp[3]

        # Solo se considera la parte del empleador para el umbral
        pen_rate_employer = data['hr_payroll_co.pen_rate_employer'] / 100
        accai_amount_threshold = smmlv * accai_threshold * pen_rate_employer * days / 30

        # Dividir el total entre público y ACCAI
        if new_line['pens_total'] <= accai_amount_threshold:
            new_line['pens_public'] = new_line['pens_total']
            new_line['pens_accai'] = 0
        else:
            new_line['pens_public'] = accai_amount_threshold
            new_line['pens_accai'] = new_line['pens_total'] - \
                accai_amount_threshold

    def _create_move_lines_for_concept(self, move_id, concept, prefix_account, amount, contract):
        """
        Crea las líneas de débito y crédito para un concepto específico
        @params:
            move_id: ID del movimiento contable
            concept: Concepto de nómina
            prefix_account: Prefijo de cuenta
            amount: Monto
            contract: Contrato
        @return:
            Tupla con (debit_line, credit_line)
        """
        debit_account, credit_account = concept.get_debit_credit_accounts(
            prefix_account)
        debit_line = self.create_regular_account_move_line(
            move_id, debit_account, 'debit', amount, contract, concept)
        credit_line = self.create_regular_account_move_line(
            move_id, credit_account, 'credit', amount, contract, concept)
        return debit_line, credit_line

    def _handle_pension_reform(self, record, move_id, amount, contract, prefix_account, ap_pens_concepts, economic_variables, politics):
        """
        Maneja la lógica de reforma de pensiones dividiendo entre público y ACCAI
        """
        lines = []

        # División de monto de pensión en público y ACCAI
        year_month = (record.period_id.start.year,
                      record.period_id.start.month)
        smmlv = economic_variables['SMMLV'][year_month]
        accai_th = economic_variables['ACCAI_THRESHOLD'][year_month]
        pen_rate_employer = politics['hr_payroll_co.pen_rate_employer'] / 100
        amount_accai_pens_th = smmlv * accai_th * pen_rate_employer

        if amount <= amount_accai_pens_th:
            amount_public = amount
            amount_accai = 0
        else:
            amount_public = amount_accai_pens_th
            amount_accai = amount - amount_accai_pens_th

        # Crear líneas para público
        if amount_public > 0:
            ap_pens_public_concept = ap_pens_concepts['AP_PENS_PUBLIC']
            debit_line, credit_line = self._create_move_lines_for_concept(
                move_id, ap_pens_public_concept, prefix_account, amount_public, contract)
            lines.extend([debit_line, credit_line])

        # Crear líneas para ACCAI
        if amount_accai > 0:
            ap_pens_accai_concept = ap_pens_concepts['AP_PENS_ACCAI']
            debit_line, credit_line = self._create_move_lines_for_concept(
                move_id, ap_pens_accai_concept, prefix_account, amount_accai, contract)
            lines.extend([debit_line, credit_line])

        return lines

    def create_regular_account_move_line(self, move_id, account_id, type, amount, contract, concept):
        debit_amount, credit_amount = 0, 0
        if type == 'debit':
            debit_amount = amount
        if type == 'credit':
            credit_amount = amount

        partner_id = concept.get_partner_id(contract)
        aml_name = contract.employee_id.partner_id.vat or concept.name
        analytic_distribution = self._get_distribution(contract, account_id)

        return {
            'account_id': account_id.id,
            'partner_id': partner_id,
            'name': aml_name,
            'debit': debit_amount,
            'credit': credit_amount,
            'move_id': move_id,
            'currency_id': self.company_id.currency_id.id,
            'analytic_distribution': analytic_distribution
        }

    def create_prod_line(self,cr, economic_variables, contract, period, lines_pila):
        new_data = {}
        self.get_data(
                new_data, cr, economic_variables, contract, period, lines_pila)
