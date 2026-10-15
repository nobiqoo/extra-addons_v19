# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

CONCEPTS = [
    ('leave', 'Ausencia'),
    ('novelty', 'Novedad'),
    ('overtime', 'Hora extra'),
    ('payslip', 'Nómina'),
    ('external', 'Externo'),
]

class IncomeAndWithholdingCertificate(models.Model):
    _name = 'income.and.withholding.concepts'
    _description = 'Income and withholding concepts'

    name = fields.Char('Nombre')
    type = fields.Selection(CONCEPTS, string='Tipo')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)

    @api.depends()
    def _compute_display_name(self):
        def get_type_value(type):
            return next(filter(lambda x: x[0] == type, CONCEPTS), ('', ''))[1]
        for record in self:
            record.display_name = f'{record.name}-{get_type_value(record.type)}'

    @api.model
    def load(self):
        query = '''
        INSERT INTO income_and_withholding_concepts (name, type, company_id)
        WITH 
            native_concepts AS (
                SELECT name, 'leave' AS type, company_id FROM hr_leave_type
                UNION ALL
                SELECT name, 'novelty' AS type, company_id FROM hr_novelty_type
                UNION ALL
                SELECT name, 'overtime' AS type, company_id FROM hr_overtime_type
                UNION ALL
                SELECT name, 'payslip' AS type, company_id FROM hr_concept
            ),
            external_concepts AS (
                SELECT HPL.name, 'external' AS type, HP.company_id
                FROM hr_payslip_line AS HPL
                INNER JOIN hr_payslip AS HP
                    ON HP.id = HPL.payslip_id
                WHERE 
                    HPL.concept_id IS NULL and
                    HPL.leave_id IS NULL and
                    HPL.overtime_id IS NULL and
                    HPL.novelty_id IS NULL
                GROUP BY HPL.name, HP.company_id
            ),
            concepts AS (
                SELECT name, type, company_id from native_concepts
                UNION ALL
                SELECT name, type, company_id from external_concepts
            )
        SELECT CC.name, CC.type, CC.company_id
        FROM concepts AS CC
        LEFT JOIN income_and_withholding_concepts AS IWC
            ON IWC.name = CC.name AND  IWC.type = CC.type AND IWC.company_id = CC.company_id
        WHERE IWC.id IS NULL AND CC.company_id = %(company_id)s;
        '''
        params = {'company_id': self.env.company.id}
        self._cr.execute(query, params)
        integral_salary = '''
        INSERT INTO income_and_withholding_concepts (name, type, company_id)
        SELECT 'SUELDO BASICO INTEGRAL', 'payslip', %(company_id)s
        WHERE NOT EXISTS (
            SELECT 1
            FROM income_and_withholding_concepts
            WHERE name = 'SUELDO BASICO INTEGRAL'
            AND company_id = %(company_id)s
        );
        '''
        self._cr.execute(integral_salary, params)
        sen_elective = '''
        INSERT INTO income_and_withholding_concepts (name, type, company_id)
        SELECT 'CUOTA DE SOSTENIMIENTO LECTIVO', 'payslip', %(company_id)s
        WHERE NOT EXISTS (
            SELECT 1
            FROM income_and_withholding_concepts
            WHERE name = 'CUOTA DE SOSTENIMIENTO LECTIVO'
            AND company_id = %(company_id)s
        );
        '''
        self._cr.execute(sen_elective, params)
        sen_prod = '''
        INSERT INTO income_and_withholding_concepts (name, type, company_id)
        SELECT 'CUOTA DE SOSTENIMIENTO PRODUCTIVO', 'payslip', %(company_id)s
        WHERE NOT EXISTS (
            SELECT 1
            FROM income_and_withholding_concepts
            WHERE name = 'CUOTA DE SOSTENIMIENTO PRODUCTIVO'
            AND company_id = %(company_id)s
        );
        '''
        self._cr.execute(sen_prod, params)
