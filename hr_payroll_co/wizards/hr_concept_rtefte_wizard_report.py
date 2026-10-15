# -*- coding: utf-8 -*-
from odoo import models


class HrConceptRtefteWizardReport(models.TransientModel):
    _name = 'hr.concept.rtefte.wizard.report'
    _description = 'Reporte de conceptos de retención en la fuente'
    _inherit = 'hr.concept.wizard.report'

    def clean_data(self):
        self.env.cr.execute(f'''
            DELETE FROM hr_concept_rtefte
            WHERE user_id = {self.env.uid} OR user_id IS NULL''')

    def show_previous_report(self):
        return {
            'name': 'Reporte de conceptos de retención en la fuente',
            'res_model': 'hr.concept.rtefte',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form,search',
            'domain': [('user_id', '=', self.env.uid), ('company_id', '=', self.env.company.id)],
        }

    def get_query_params(self):
        filters = [
            self.build_period_filter(),
            self.build_contracts_filter(),
            self.build_contracts_groups_filter(),
        ]

        query_params = {}
        [query_params.update(params) for _, params in filters]
        clauses = 'AND '.join([clause for clause, _ in filters if clause])
        return clauses, query_params

    def get_query(self, clauses):
        return f'''
        INSERT INTO hr_concept_rtefte (
            name,
            company_id,
            period_id,
            payslip_id,
            employee_id,
            contract_id,
            payslip_processing_id,
            contract_date_start,
            contract_settlement_date,
            wage,
            contract_duration,
            earnings,
            o_earnings,
            o_salarial_earnings,
            comp_earnings,
            o_rights,
            income_ext,
            apply_procedure_2,
            prima,
            prima_liq,
            total_income,
            ded_pens,
            ded_eps,
            fond_sol,
            fond_sub,
            total_nci,
            neto_income,
            current_year,
            uvt,
            deduction_dependents,
            deduction_estate,
            deduction_healthcare,
            deduction_icetex,
            deduction_total,
            avp,
            afc,
            voluntary_contributions,
            annual_top25,
            top25_monthly,
            top25_total,
            annual_top40,
            top40_monthly,
            top40_total,
            exempt_rent,
            brtf,
            rate,
            rtefte,
            user_id
        )
        SELECT 
            'RTEFTE - ' || HC.name || ' - ' || HPP.name as name,
            HP.company_id,
            L.period_id,
            L.payslip_id,
            L.employee_id,
            L.contract_id,
            L.payslip_processing_id,
            L.date_from as contract_date_start,
            L.date_to as contract_settlement_date,
            L.total_salary as wage,
            L.contract_duration,

            L.total_earnings as earnings,
            L.total_o_earnings as o_earnings,
            L.total_o_salarial_earnings as o_salarial_earnings,
            L.total_comp_earnings as comp_earnings,
            L.total_o_rights as o_rights,

            L.rtefte_income_ext as income_ext,
            L.rtefte_apply_procedure_2 as apply_procedure_2,
            L.rtefte_prima as prima,
            L.rtefte_prima_liq as prima_liq,
            L.rtefte_total_income as total_income,
            L.rtefte_ded_pens as ded_pens,
            L.rtefte_ded_eps as ded_eps,
            L.rtefte_fond_sol as fond_sol,
            L.rtefte_fond_sub as fond_sub,
            L.rtefte_total_nci as total_nci,
            L.rtefte_neto_income as neto_income,
            L.rtefte_current_year as current_year,
            L.rtefte_uvt as uvt,
            L.rtefte_deduction_dependents as deduction_dependents,
            L.rtefte_deduction_estate as deduction_estate,
            L.rtefte_deduction_healthcare as deduction_healthcare,
            L.rtefte_deduction_icetex as deduction_icetex,
            L.rtefte_deduction_total as deduction_total,
            L.rtefte_avp as avp,
            L.rtefte_afc as afc,
            L.rtefte_voluntary_contributions as voluntary_contributions,
            L.rtefte_annual_top25 as annual_top25,
            L.rtefte_top25_monthly as top25_monthly,
            L.rtefte_top25_total as top25_total,
            L.rtefte_annual_top40 as annual_top40,
            L.rtefte_top40_monthly as top40_monthly,
            L.rtefte_top40_total as top40_total,
            L.rtefte_exempt_rent as exempt_rent,

            L.total_base as brtf,
            L.rate,
            L.total as rtefte,
            {self.env.uid} as user_id
        FROM hr_payslip_line_log AS L
        INNER JOIN hr_concept AS HCP ON HCP.id = L.concept_id
        INNER JOIN hr_payslip AS HP ON HP.id = L.payslip_id
        INNER JOIN hr_period AS HPP ON HPP.id = L.period_id
        INNER JOIN hr_contract AS HC ON HC.id = L.contract_id
        LEFT JOIN hr_contract_group AS HCG ON HCG.id = HC.contract_group_id
        WHERE 
            HCP.code = 'RTEFTE'
            AND HP.state = 'paid'
            AND HP.company_id = {self.env.company.id}
            {f'AND {clauses}' if clauses else ''}
        ON CONFLICT (payslip_id, user_id) DO NOTHING;
        '''
