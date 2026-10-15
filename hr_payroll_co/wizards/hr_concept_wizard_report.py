# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import ValidationError
from ..models.hr_payslip_noveltys.model_basic_payslip_novelty_type import CATEGORY_PAYSLIP
from ..models.hr_payslip.hr_payslip import STATE

SEARCH_TYPES = [
    ('unique', 'Único'),
    ('range', 'Rango')
]


class HrConceptWizardReport(models.TransientModel):
    _name = 'hr.concept.wizard.report'
    _description = 'Reporte de conceptos de nómina'

    contracts_ids = fields.Many2many(
        comodel_name='hr.contract', string='Contratos')
    contract_groups_ids = fields.Many2many(
        comodel_name='hr.contract.group', string='Grupos de contratos')
    search_type = fields.Selection(
        string='Tipo de busqueda', selection=SEARCH_TYPES, default='unique', required=True)

    period_id = fields.Many2one(comodel_name='hr.period', string='Periodo')
    from_period_id = fields.Many2one(comodel_name='hr.period', string='Desde')
    to_period_id = fields.Many2one(comodel_name='hr.period', string='Hasta')

    payslip_category = fields.Selection(
        string='Categoría de conceptos', selection=CATEGORY_PAYSLIP)
    payslip_state = fields.Selection(string='Estado', selection=STATE)
    payslip_types_ids = fields.Many2many(
        comodel_name='hr.payslip.type', string='Tipos de nómina')

    def show_report(self):
        self.clean_data()
        self.build_report()
        return self.show_previous_report()

    def show_previous_report(self):
        return {
            'name': 'Reporte de conceptos de nómina',
            'res_model': 'hr.payslip.concept.report',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,pivot,graph',
            'domain': [('user_id', '=', self.env.uid), ('company_id', '=', self.env.company.id)],
        }

    def clean_data(self):
        self.env.cr.execute(f'''
            DELETE FROM hr_payslip_concept_report
            WHERE user_id = {self.env.uid}''')

    def build_report(self):
        clauses, query_params = self.get_query_params()
        query = self.get_query(clauses)
        self.env.cr.execute(query, query_params)
        return

    def get_query_params(self):
        filters = [
            self.build_period_filter(),
            self.build_contracts_filter(),
            self.build_contracts_groups_filter(),
            self.build_category_filter(),
            self.build_state_filter(),
            self.build_payslip_type_filter(),
        ]

        query_params = {}
        [query_params.update(params) for _, params in filters]
        clauses = 'AND '.join([clause for clause, _ in filters if clause])
        return clauses, query_params

    def get_query(self, clauses):
        return f'''
        INSERT INTO hr_payslip_concept_report (
            user_id,
            company_id,

            employee,
            employee_id,
            vat,
            contract,
            contract_id,
            contract_group,
            contract_date_start,
            contract_settlement_date,
            contract_schedule_pay,
            contract_wage,
            payslip_type,
            payslip_period,
            payslip_liquidation_date,
            payslip_accounting_date,

            payslip_line,
            payslip_category,
            payslip_line_qty,
            payslip_line_value,
            payslip_line_total,

            novelty,
            novelty_type,

            leave,
            code_cie10,
            description_cie10,
            leave_actual_start_date,
            leave_actual_end_date,
            leave_type,
            leave_date_start,
            leave_date_end,

            overtime,
            overtime_type,

            bank_id,
            bank_account,
            concept_id,
            l10n_latam_identification_type_id,
            payslip_state
        )
        (
            SELECT 

                {self.env.uid},
                HP.company_id,
            
                HE.name AS "Empleado",
                HE.id AS "Empleado ID",
                RP.vat AS "Número de identificación",
                HC.name AS "Contrato",
                HC.id AS "Contrato ID",
                HCG.name AS "Grupo de contrato",
                HC.date_start AS "Inicio de contrato",
                HC.settlement_date AS "Liquidación de contrato",
                CASE
                    WHEN HC.schedule_pay = 'MONTHLY' THEN 'Mensual'
                    WHEN HC.schedule_pay = 'BIWEEKLY' THEN 'Quincenal'
                    ELSE HC.schedule_pay
                END AS "Pago",
                HC.wage AS "Salario",

                HPT.name AS "Tipo de nómina",
                HPP.name AS "Periodo de nómina",
                hp.liquidation_date AS "Liquidación de nómina",
                hp.accounting_date AS "Contabilización de nómina",

                HPL.name AS "Concepto",
                CASE 
                    WHEN HPL.concept_id IS NOT NULL THEN HCP.category
                    WHEN HPL.novelty_id IS NOT NULL THEN HNT.category
                    WHEN HPL.leave_id IS NOT NULL THEN HLT.category
                    WHEN HPL.overtime_id IS NOT NULL THEN HOT.category
                    WHEN HPL.category IS NOT NULL THEN HPL.category
                    ELSE 'no_category'
                END AS "Categoría de concepto",
                HPL.qty AS "Cantidad",
                HPL.value AS "Valor",
                HPL.total AS "Total",

                HN.name AS "Novedad",
                HNT.name AS "Categoría de novedad",

                HL.name AS "Ausencia",
                HCC.code AS "Código CIE10",
                HL.diagnosis_description AS "Descripción del diagnóstico",
                HL.actual_start_date AS "Fecha Real de Inicio",
                HL.actual_end_date AS "Fecha Real de Fin",
                HLT.name AS "Categoría de ausencia",
                HL.date_start AS "Inicio de ausencia",
                HL.date_end AS "Fin de ausencia",

                HO.name AS "Hora extra",
                HOT.name AS "Categoría de hora extra",
                RPB.bank_id AS "Banco",
                RPB.acc_number AS "Número de cuenta bancaria",
                HCP.id AS "Concepto",
                LLIT.id AS "Tipo de Documento",
                HP.state AS "Estado nómina"

            FROM hr_payslip_line AS HPL

            LEFT JOIN hr_payslip AS HP       ON HP.id = HPL.payslip_id
            LEFT JOIN hr_payslip_type AS HPT ON HPT.id = HP.payslip_type_id
            LEFT JOIN hr_period AS HPP       ON HPP.id = HP.period_id

            LEFT JOIN hr_contract AS HC         ON HC.id = HP.contract_id
            LEFT JOIN hr_contract_group AS HCG  ON HCG.id = HC.contract_group_id
            LEFT JOIN hr_employee AS HE         ON HE.id = HC.employee_id
            LEFT JOIN res_partner AS RP         ON RP.id = HE.partner_id

            LEFT JOIN hr_novelty AS HN  ON HN.id = HPL.novelty_id
            LEFT JOIN hr_leave AS HL    ON HL.id = HPL.leave_id
            LEFT JOIN hr_leave_code_cie10_table AS HCC ON HCC.id = HL.code_cie10_id
            LEFT JOIN hr_overtime AS HO ON HO.id = HPL.overtime_id

            LEFT JOIN hr_novelty_type AS HNT  ON HNT.id = HN.novelty_type_id
            LEFT JOIN hr_leave_type AS HLT    ON HLT.id = HL.leave_type_id
            LEFT JOIN hr_overtime_type AS HOT ON HOT.id = HO.overtime_type_id

            LEFT JOIN hr_concept AS HCP ON HCP.id = HPL.concept_id
            LEFT JOIN res_partner_bank AS RPB ON RPB.id = RP.main_bank_id
            LEFT JOIN l10n_latam_identification_type AS LLIT ON LLIT.id = RP.l10n_latam_identification_type_id

            WHERE 
                {clauses}
            ORDER BY HC.name, HPP.name, HPL.name
        )
        '''

    def build_period_filter(self):
        query_params = {}
        if self.search_type == 'unique':
            if not self.period_id:
                raise ValidationError('Debe configurar el periodo')

            clause = 'HPP.start >= %(start)s AND HPP.end <= %(end)s '
            query_params['start'] = self.period_id.start
            query_params['end'] = self.period_id.end
        else:
            if not self.from_period_id or not self.to_period_id:
                raise ValidationError('Debe configurar el rango desde y hasta')

            start = self.from_period_id.start
            end = self.to_period_id.end
            if start > end:
                raise ValidationError(
                    'La fecha de fin debe ser mayor a la fecha de inicio')

            clause = 'HPP.start >= %(start)s AND HPP.end <= %(end)s '
            query_params['start'] = start
            query_params['end'] = end

        return clause, query_params

    def build_contracts_filter(self):
        contracts = self.contracts_ids.ids
        if not contracts:
            return '', {}
        elif len(contracts) == 1:
            return 'HC.id = %(contract)s ', {'contract': contracts[0]}
        else:
            return 'HC.id IN %(contracts)s ', {'contracts': tuple(contracts)}

    def build_contracts_groups_filter(self):
        groups = self.contract_groups_ids.ids
        if not groups:
            return '', {}
        elif len(groups) == 1:
            return 'HCG.id = %(group)s ', {'group': groups[0]}
        else:
            return 'HCG.id IN %(groups)s ', {'groups': tuple(groups)}

    def build_category_filter(self):
        if not self.payslip_category:
            return '', {}
        return 'HPL.category = %(category)s ', {'category': self.payslip_category}

    def build_state_filter(self):
        if not self.payslip_state:
            return '', {}
        return 'HP.state = %(state)s ', {'state': self.payslip_state}

    def build_payslip_type_filter(self):
        types = self.payslip_types_ids.ids
        if not types:
            return '', {}
        elif len(types) == 1:
            return 'HPT.id = %(types)s ', {'types': types[0]}
        else:
            return 'HPT.id IN %(types)s ', {'types': tuple(types)}
