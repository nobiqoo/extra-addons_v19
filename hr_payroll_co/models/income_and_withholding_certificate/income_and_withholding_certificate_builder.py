# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

SEQUENCE_CODE = 'seg.income.and.withholding.certificate'
LOGGER = logging.getLogger(__name__)


class IncomeAndWithholdingCertificateBuilder(models.TransientModel):
    _name = 'income.and.withholding.certificate.builder'
    _description = 'Income and withholding certificate builder'

    company_id = fields.Many2one(
        'res.company', string='Compañía', default=lambda self: self.env.company, readonly=True)
    date = fields.Date('Fecha', required=True)
    contracts_ids = fields.Many2many(
        'hr.contract', string='Contratos', domain="[('company_id', '=', company_id)]")
    city_id = fields.Many2one(
        'res.city', string='Ciudad/Municipio', required=True)
    template_id = fields.Many2one(
        'income.and.withholding.certificate.template', string='Plantilla', required=True)
    unify_by_employee = fields.Boolean(
        string='Unificar por empleado', default=False)

    @api.onchange('date')
    def _date_onchange_(self):
        self.template_id = False
        domain = self.build_template_domain()
        return {'domain': {'template_id': domain}}

    def build_template_domain(self):
        domain = [('company_id', '=', self.env.company.id)]
        if not self.date:
            return domain

        date_from = self.date.replace(month=1, day=1)
        domain += [
            ('template_date', '<=', self.date),
            ('template_date', '>=', date_from),
        ]
        return domain

    def create_certificate(self):
        if len(self.contracts_ids) == 0:
            raise ValidationError('Agregue uno o más contratos')

        date_from = self.date.replace(year=self.date.year-1, month=1, day=1)
        date_to = self.date.replace(year=self.date.year-1, month=12, day=31)
        concepts = self.get_concepts(
            date_from, date_to, tuple(self.contracts_ids.ids), self.template_id)

        company = self.env.company
        certificate_template = {
            'template_id': self.template_id.id,
            'nit': company.partner_id.vat,
            'verification_code': company.partner_id.l10n_co_verification_code,
            'social_reason': company.partner_id.name,
            'retainer': company.partner_id.name,

            'year': '{:04d}'.format(self.date.year-1),

            'date_from_year': '{:04d}'.format(date_from.year),
            'date_from_month': '{:02d}'.format(date_from.month),
            'date_from_day': '{:02d}'.format(date_from.day),

            'date_to_year': '{:04d}'.format(date_to.year),
            'date_to_month': '{:02d}'.format(date_to.month),
            'date_to_day': '{:02d}'.format(date_to.day),

            'date_year': '{:04d}'.format(self.date.year),
            'date_month': '{:02d}'.format(self.date.month),
            'date_day': '{:02d}'.format(self.date.day),
        }
        if not company.partner_id.is_company:
            certificate_template['retainer_first_last_name'] = company.partner_id.lastname1
            certificate_template['retainer_second_last_name'] = company.partner_id.lastname2
            certificate_template['retainer_first_name'] = company.partner_id.name1
            certificate_template['retainer_second_name'] = company.partner_id.name2

        certificates = []
        employees_vat = []

        for contract_id in self.contracts_ids:
            certficate, is_child = self.build_certificate(
                certificate_template, company, date_from, date_to, contract_id, concepts, certificates, employees_vat)
            if is_child:
                continue
            certificates.append(certficate)

        if all(not x for x in certificates):
            raise ValidationError('No se generó ningún certificado porque los contratos seleccionados no tienen información de retención en la fuente para mostrar en el período especificado.')

        certificates = self.env['income.and.withholding.certificate'].sudo(
        ).create(list(filter(lambda c: c, certificates)))

        return {
            'name': "Certificados creados",
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'income.and.withholding.certificate',
            'domain': [('id', 'in', certificates.ids)],
        }

    def get_concepts(self, date_from, date_to, contracts_ids, template):
        subquerys = [
            self.build_subquerys(
                "salary_payments", template.salary_payments.ids),
            self.build_subquerys(
                "bonus_payments", template.bonus_payments.ids),
            self.build_subquerys(
                "food_payments", template.food_payments.ids),
            self.build_subquerys(
                "fee_payments", template.fee_payments.ids),
            self.build_subquerys(
                "service_payments", template.service_payments.ids),
            self.build_subquerys(
                "commission_payments", template.commission_payments.ids),
            self.build_subquerys(
                "social_benefit_payments", template.social_benefit_payments.ids),
            self.build_subquerys(
                "travel_payments", template.travel_payments.ids),
            self.build_subquerys(
                "proxy_payments", template.proxy_payments.ids),
            self.build_subquerys(
                "cooperative_work_payments", template.cooperative_work_payments.ids),
            self.build_subquerys(
                "other_payments", template.other_payments.ids),
            self.build_subquerys(
                "severance_payments", template.severance_payments.ids),
            self.build_subquerys(
                "severance_cst_payments", template.severance_cst_payments.ids),
            self.build_subquerys(
                "severance_fund_payments", template.severance_fund_payments.ids),
            self.build_subquerys(
                "pension_payments", template.pension_payments.ids),
            self.build_subquerys(
                "financial_support_payments", template.financial_support_payments.ids),
            self.build_subquerys(
                "health_contributions", template.health_contributions.ids),
            self.build_subquerys(
                "pension_contributions", template.pension_contributions.ids),
            self.build_subquerys(
                "voluntary_contributions_rais", template.voluntary_contributions_rais.ids),
            self.build_subquerys(
                "afp_contribution", template.afp_contribution.ids),
            self.build_subquerys(
                "afc_contributions", template.afc_contributions.ids),
            self.build_subquerys(
                "avc_contributions", template.avc_contributions.ids),
            self.build_subquerys(
                "withholding_tax", template.withholding_tax.ids),
        ]

        if all(not subquery for subquery in subquerys):
            raise ValidationError(
                'No se han configurados los conceptos de la plantilla')

        subtotals_query = []
        for subquery in filter(lambda sq: sq, subquerys):
            subtotals_query.append(subquery['subtotal_query'])

        query = f'''
        WITH 
            payslips AS (
                SELECT HP.id, HP.contract_id
                FROM hr_payslip AS HP
                INNER JOIN hr_period AS PP
                    ON PP.id = HP.period_id
                WHERE 
                    HP.contract_id IN %(contracts_ids)s AND
                    HP.state = 'paid' AND
                    PP.start <= %(date_to)s AND PP.end >= %(date_from)s

            ),
            contracts AS (
                SELECT contract_id AS id FROM payslips GROUP BY contract_id
            ),
            normalized_payslip_lines AS (
                SELECT  HP.contract_id, 
                        COALESCE(HC.name,
                                 HNT.name,
                                 HLT.name,
                                 HOT.name,
                                 HPL.name,
                                 '-') AS name,
                        CASE
                            WHEN HC.id IS NOT NULL THEN 'payslip'
                            WHEN HNT.id IS NOT NULL THEN 'novelty'
                            WHEN HLT.id IS NOT NULL THEN 'leave'
                            WHEN HOT.id IS NOT NULL THEN 'overtime'
                            ELSE 'external'
                        END AS type,
                        COALESCE(HPL.total, 0) AS total
                FROM hr_payslip_line AS HPL
                INNER JOIN payslips AS HP ON HP.id = HPL.payslip_id
                LEFT JOIN hr_concept AS HC ON HC.id = HPL.concept_id
                LEFT JOIN hr_novelty AS HN ON HN.id = HPL.novelty_id
                LEFT JOIN hr_novelty_type AS HNT ON HNT.id = HN.novelty_type_id
                LEFT JOIN hr_leave AS HL ON HL.id = HPL.leave_id
                LEFT JOIN hr_leave_type AS HLT ON HLT.id = HL.leave_type_id
                LEFT JOIN hr_overtime AS HO ON HO.id = HPL.overtime_id
                LEFT JOIN hr_overtime_type AS HOT ON HOT.id = HO.overtime_type_id

            ),
            concept_mapping AS (
                {'UNION'.join(subtotals_query)}
            )
        SELECT
            NPL.contract_id,
            CM.field,
            SUM(NPL.total) AS total

        FROM normalized_payslip_lines NPL
        INNER JOIN concept_mapping CM
            ON CM.name = NPL.name
            AND CM.type = NPL.type
        GROUP BY
            NPL.contract_id,
            CM.field
        '''

        params = {
            'contracts_ids': contracts_ids,
            'date_from': date_from,
            'date_to': date_to
        }
        self._cr.execute(query, params)
        concepts = {}
        for row in self._cr.dictfetchall():
            contract = row['contract_id']
            concepts.setdefault(contract, {'contract_id': contract})[row['field']] = row['total']
        return concepts

    def build_subquerys(self, alias, concepts_ids):
        if not concepts_ids:
            return {}
        if len(concepts_ids) == 1:
            concepts_ids.append(0)
        subtotal_query = f'''
            SELECT
                id,
                name,
                type,
                '{alias}' AS field
            FROM income_and_withholding_concepts
            WHERE id IN {tuple(concepts_ids)}
        '''
        return {
            'subtotal_query': subtotal_query,
            'field_query': '' # field_query
        }

    def build_certificate(self, certificate_template, company, date_from, date_to, contract_id, concepts, certificates, employees_vat):
        employee_subtotals = concepts.get(contract_id.id, {})
        if not employee_subtotals:
            LOGGER.info(
                f"Se descarta el contrato {contract_id.id} por falta de conceptos")
            return {}, False

        employee_partner_id = contract_id.employee_id.partner_id
        certificate = certificate_template.copy()
        required_unify = False
        is_child = False
        if employee_partner_id.vat not in employees_vat:
            employees_vat.append(employee_partner_id.vat)
        else:
            required_unify = True if self.unify_by_employee else False

        if not required_unify:
            certificate['partner_id'] = employee_partner_id.id
            certificate['form_number'] = self.get_sequence(company) if not required_unify else ''
            certificate['employee_document_type'] = employee_partner_id.l10n_latam_identification_type_id.dian_code if employee_partner_id.l10n_latam_identification_type_id else ''
            certificate['employee_vat'] = employee_partner_id.vat or ''
            certificate['employee_first_last_name'] = employee_partner_id.lastname1 or ''
            certificate['employee_second_last_name'] = employee_partner_id.lastname2 or ''
            certificate['employee_first_name'] = employee_partner_id.name1 or ''
            certificate['employee_second_name'] = employee_partner_id.name2 or ''

            certificate['holding_place'] = f'{self.city_id.name}-{self.city_id.state_id.name}'
            certificate['departament_code'] = self.city_id.state_id.dian_code or ''
            certificate['city_code'] = self.city_id.dian_code[2:] if self.city_id.dian_code and len(self.city_id.dian_code) > 2 else ''

            certificate['salary_payments'] = employee_subtotals.get(
                'salary_payments', 0)
            certificate['bonus_payments'] = employee_subtotals.get(
                'bonus_payments', 0)
            certificate['food_payments'] = employee_subtotals.get(
                'food_payments', 0)
            certificate['fee_payments'] = employee_subtotals.get(
                'fee_payments', 0)
            certificate['service_payments'] = employee_subtotals.get(
                'service_payments', 0)
            certificate['commission_payments'] = employee_subtotals.get(
                'commission_payments', 0)
            certificate['social_benefit_payments'] = employee_subtotals.get(
                'social_benefit_payments', 0)
            certificate['travel_payments'] = employee_subtotals.get(
                'travel_payments', 0)
            certificate['proxy_payments'] = employee_subtotals.get(
                'proxy_payments', 0)
            certificate['cooperative_work_payments'] = employee_subtotals.get(
                'cooperative_work_payments', 0)
            certificate['other_payments'] = employee_subtotals.get(
                'other_payments', 0)
            certificate['severance_payments'] = employee_subtotals.get(
                'severance_payments', 0)
            certificate['severance_cst_payments'] = employee_subtotals.get(
                'severance_cst_payments', 0)
            certificate['severance_fund_payments'] = employee_subtotals.get(
                'severance_fund_payments', 0)
            certificate['pension_payments'] = employee_subtotals.get(
                'pension_payments', 0)
            certificate['financial_support_payments'] = employee_subtotals.get(
                'financial_support_payments', 0)

            certificate['health_contributions'] = employee_subtotals.get(
                'health_contributions', 0)
            certificate['pension_contributions'] = employee_subtotals.get(
                'pension_contributions', 0)
            certificate['voluntary_contributions_rais'] = employee_subtotals.get(
                'voluntary_contributions_rais', 0)
            certificate['afp_contribution'] = employee_subtotals.get(
                'afp_contribution', 0)
            certificate['afc_contributions'] = employee_subtotals.get(
                'afc_contributions', 0)
            certificate['avc_contributions'] = employee_subtotals.get(
                'avc_contributions', 0)

            certificate['withholding_tax'] = employee_subtotals.get(
                'withholding_tax', 0)
            certificate['retainer'] = company.partner_id.name

            payment_concepts = [
                'salary_payments', 'bonus_payments', 'food_payments', 'fee_payments', 'service_payments', 'commission_payments',
                'social_benefit_payments', 'travel_payments', 'proxy_payments', 'cooperative_work_payments', 'other_payments',
                'severance_payments', 'severance_cst_payments', 'severance_fund_payments', 'pension_payments', 'financial_support_payments'
            ]
            certificate['total_payments'] = sum(
                [v for k, v in certificate.items() if k in payment_concepts and isinstance(v, (int, float)) and v])

            certificate['average_salary'] = self._compute_average_salary(
                contract_id, date_from, date_to)
        else:
            is_child = True
            certificate = self._get_parent_certificate(employee_partner_id.vat, certificates)
            current_certificate = certificate_template.copy()

            certificate['salary_payments'] += employee_subtotals.get(
                'salary_payments', 0)
            certificate['bonus_payments'] += employee_subtotals.get(
                'bonus_payments', 0)
            certificate['food_payments'] += employee_subtotals.get(
                'food_payments', 0)
            certificate['fee_payments'] += employee_subtotals.get(
                'fee_payments', 0)
            certificate['service_payments'] += employee_subtotals.get(
                'service_payments', 0)
            certificate['commission_payments'] += employee_subtotals.get(
                'commission_payments', 0)
            certificate['social_benefit_payments'] += employee_subtotals.get(
                'social_benefit_payments', 0)
            certificate['travel_payments'] += employee_subtotals.get(
                'travel_payments', 0)
            certificate['proxy_payments'] += employee_subtotals.get(
                'proxy_payments', 0)
            certificate['cooperative_work_payments'] += employee_subtotals.get(
                'cooperative_work_payments', 0)
            certificate['other_payments'] += employee_subtotals.get(
                'other_payments', 0)
            certificate['severance_payments'] += employee_subtotals.get(
                'severance_payments', 0)
            certificate['severance_cst_payments'] += employee_subtotals.get(
                'severance_cst_payments', 0)
            certificate['severance_fund_payments'] += employee_subtotals.get(
                'severance_fund_payments', 0)
            certificate['pension_payments'] += employee_subtotals.get(
                'pension_payments', 0)
            certificate['financial_support_payments'] += employee_subtotals.get(
                'financial_support_payments', 0)

            certificate['health_contributions'] += employee_subtotals.get(
                'health_contributions', 0)
            certificate['pension_contributions'] += employee_subtotals.get(
                'pension_contributions', 0)
            certificate['voluntary_contributions_rais'] += employee_subtotals.get(
                'voluntary_contributions_rais', 0)
            certificate['afp_contribution'] += employee_subtotals.get(
                'afp_contribution', 0)
            certificate['afc_contributions'] += employee_subtotals.get(
                'afc_contributions', 0)
            certificate['avc_contributions'] += employee_subtotals.get(
                'avc_contributions', 0)

            certificate['withholding_tax'] += employee_subtotals.get(
                'withholding_tax', 0)

            current_certificate['salary_payments'] = employee_subtotals.get(
                'salary_payments', 0)
            current_certificate['bonus_payments'] = employee_subtotals.get(
                'bonus_payments', 0)
            current_certificate['food_payments'] = employee_subtotals.get(
                'food_payments', 0)
            current_certificate['fee_payments'] = employee_subtotals.get(
                'fee_payments', 0)
            current_certificate['service_payments'] = employee_subtotals.get(
                'service_payments', 0)
            current_certificate['commission_payments'] = employee_subtotals.get(
                'commission_payments', 0)
            current_certificate['social_benefit_payments'] = employee_subtotals.get(
                'social_benefit_payments', 0)
            current_certificate['travel_payments'] = employee_subtotals.get(
                'travel_payments', 0)
            current_certificate['proxy_payments'] = employee_subtotals.get(
                'proxy_payments', 0)
            current_certificate['cooperative_work_payments'] = employee_subtotals.get(
                'cooperative_work_payments', 0)
            current_certificate['other_payments'] = employee_subtotals.get(
                'other_payments', 0)
            current_certificate['severance_payments'] = employee_subtotals.get(
                'severance_payments', 0)
            current_certificate['severance_cst_payments'] = employee_subtotals.get(
                'severance_cst_payments', 0)
            current_certificate['severance_fund_payments'] = employee_subtotals.get(
                'severance_fund_payments', 0)
            current_certificate['pension_payments'] = employee_subtotals.get(
                'pension_payments', 0)
            current_certificate['financial_support_payments'] = employee_subtotals.get(
                'financial_support_payments', 0)

            current_certificate['health_contributions'] = employee_subtotals.get(
                'health_contributions', 0)
            current_certificate['pension_contributions'] = employee_subtotals.get(
                'pension_contributions', 0)
            current_certificate['voluntary_contributions_rais'] = employee_subtotals.get(
                'voluntary_contributions_rais', 0)
            current_certificate['afp_contribution'] = employee_subtotals.get(
                'afp_contribution', 0)
            current_certificate['afc_contributions'] = employee_subtotals.get(
                'afc_contributions', 0)
            current_certificate['avc_contributions'] = employee_subtotals.get(
                'avc_contributions', 0)

            current_certificate['withholding_tax'] = employee_subtotals.get(
                'withholding_tax', 0)

            payment_concepts = [
                'salary_payments', 'bonus_payments', 'food_payments', 'fee_payments', 'service_payments', 'commission_payments',
                'social_benefit_payments', 'travel_payments', 'proxy_payments', 'cooperative_work_payments', 'other_payments',
                'severance_payments', 'severance_cst_payments', 'severance_fund_payments', 'pension_payments', 'financial_support_payments'
            ]
            certificate['total_payments'] += sum(
                [v for k, v in current_certificate.items() if k in payment_concepts and isinstance(v, (int, float)) and v])

            certificate['average_salary'] = self._compute_average_salary(
                contract_id, date_from, date_to)

        return certificate, is_child

    def _compute_average_salary(self, contract_id, date_from, date_to):
        """Campo 59: ingreso laboral promedio (num. 4 art. 206 E.T.).

        Reutiliza el motor de prestaciones sociales para obtener el promedio
        salarial del periodo certificado. Se calcula para cualquier contrato,
        independientemente de si tiene o no fecha de liquidación. Las políticas
        se cargan completas con _get_politics() porque _compute_social_benefits
        las indexa directamente y con un dict parcial falla con KeyError.
        """
        politics = self.env['hr.payslip']._get_politics()
        politics.update({
            'hr_payroll_co.discount_suspensions': True,
            'hr_payroll_co.social_benefits_with_last_wage': True,
            'hr_payroll_co.average_sub_trans': False,
        })
        data_payslip = {
            'contract': contract_id,
            'politics': politics,
            'economic_variables': {
                'SMMLV': {
                    date_to.year: self.env['economic.variable'].get_value_by_date(
                        'SMMLV', date_to)
                },
                'SUB_TRANS': {
                    date_to.year: self.env['economic.variable'].get_value_by_date(
                        'SUB_TRANS', date_to)
                }
            },
            'cr': self._cr,
            'period': {
                'start': date_from,
                'end': date_to
            }
        }
        base, qty, total = self.env['hr.concept']._compute_social_benefits(
            data_payslip, date_from, date_to)
        return total

    def get_sequence(self, company):
        sequence = self.env['ir.sequence'].search([
            ('code', '=', SEQUENCE_CODE),
            ('company_id', '=', company.id)
        ], order='id', limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].create({
                'name': "Secuencia para cetificados de ingresos y retenciones",
                'code': 'seg.income.and.withholding.certificate',
                'company_id': company.id,
                'padding': 10
            })

        return sequence._next()

    def _get_parent_certificate(self, partner_vat, certificates):
        for certificate in certificates:
            if certificate.get('employee_vat') == partner_vat:
                return certificate
        return False
