from odoo import models, fields
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from ..models.hr_payslip.hr_payslip import STATE
import base64
import io
import re
import xlsxwriter

SEARCH_TYPES = [
    ('unique', 'Único'),
    ('range', 'Rango')
]

class HrLoanPaymentWizard(models.TransientModel):
    _name = 'hr.payslip.report.wizard'
    _description = 'Reporte de nómina'

    contracts_ids = fields.Many2many(
        comodel_name='hr.contract', string='Contratos')
    contract_groups_ids = fields.Many2many(
        comodel_name='hr.contract.group', string='Grupos de contratos')
    search_type = fields.Selection(
        string='Tipo de busqueda', selection=SEARCH_TYPES, default='unique', required=True)

    period_id = fields.Many2one(comodel_name='hr.period', string='Periodo')
    from_period_id = fields.Many2one(comodel_name='hr.period', string='Desde')
    to_period_id = fields.Many2one(comodel_name='hr.period', string='Hasta')


    payslip_state = fields.Selection(string='Estado', selection=STATE, default='paid')
    payslip_types_ids = fields.Many2many(
        comodel_name='hr.payslip.type', string='Tipos de nómina')

    template_id = fields.Many2one(
        comodel_name='hr.payslip.report.setting', string='Plantilla')

    def make_report_xlsx(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Informe de nómina")

        label_format = workbook.add_format({'border': 1})
        qty_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        money_format = workbook.add_format({'num_format': '$#,##0.00', 'border': 1})
        merge_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#D9D9D9', 'border': 1})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1, 'align': 'center'})

        headers = [
            'NUMERO DOCUMENTO', 'NOMBRE COMPLETO', 'CARGO', 'CECOS PRINCIPAL', 'REF CECOS PRINCIPAL', 'GRUPO DE CONTRATO', 'SALARIO'
        ]

        col = 0

        for col_num, header in enumerate(headers):
            worksheet.merge_range(0, col_num, 2, col_num, header, merge_format)
            col+=1
        
        earnings_line = self._get_colums(self.template_id, 'earning')
        deductions_line = self._get_colums(self.template_id, 'deduction')
        nets_line = self._get_colums(self.template_id, 'net')

        columnas = [
            ("DEVENGADO", earnings_line),
            ("TOTAL DEVENGOS", []),
            ("DEDUCCIONES", deductions_line),
            ("TOTAL DEDUCCIONES", []),
            ("NETOS", nets_line)
        ]

        for categoria, subitems in columnas:
            if not subitems:
                worksheet.merge_range(0, col, 2, col, categoria, merge_format)
                col += 1
            else:
                span = len(subitems) * 2
                worksheet.merge_range(0, col, 0, col + span - 1, categoria, merge_format)
                for sub in subitems:
                    worksheet.merge_range(1, col, 1, col + 1, sub.name.upper(), header_format)
                    worksheet.write(2, col, "Cantidad", header_format)
                    worksheet.write(2, col + 1, "Total", header_format)
                    col += 2
        
        row = 3
        datas = self.get_data()
        for data in datas:
            col = 0
            for value in data.values():
                if type(value) == str:
                    worksheet.write(row, col, value, label_format)
                    col += 1
                elif type(value) == float:
                    worksheet.write(row, col, value, money_format)
                    col += 1
                elif type(value) == dict:
                    worksheet.write(row, col, value.get('qty', 0.0), qty_format)
                    col += 1
                    worksheet.write(row, col, value.get('amount', 0.0), money_format)
                    col += 1
            row += 1

        workbook.close()
        output.seek(0)

        # Guardar el archivo en el wizard
        attachment = self.env['ir.attachment'].create({
            'name': 'Reporte_Nomina.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'hr.payslip.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            "type": "ir.actions.act_url",
            "url": '/web/content/%s?download=true' % attachment.id,
            "target": "self",
        }

    def get_data(self):
        if self.search_type == 'unique':
            date_from = self.period_id.start
            date_end = self.period_id.end
        else:
            date_from = self.from_period_id.start
            date_end = self.to_period_id.end
        domain_contracts = [
            ('company_id', '=', self.env.company.id),
            ('state', 'not in', ('draft', 'cancel'))
        ]
        if self.contracts_ids:
            domain_contracts.append(('id', 'in', self.contracts_ids.ids))
        if self.contract_groups_ids:
            domain_contracts.append(('contract_group_id', 'in', self.contract_groups_ids.ids))
        if self.payslip_types_ids:
            payslip_type_ids = self.payslip_types_ids
        else:
            payslip_type_ids = self.env['hr.payslip.type'].search([])
        contracts = self.env['hr.contract'].search(domain_contracts)
        concepts = self.get_concepts(date_from, date_end, tuple(contracts.ids), tuple(payslip_type_ids.ids), self.template_id)
        data = []
        for concept in concepts:
            total_earnings = 0
            total_deductions = 0
            contract = self.env['hr.contract'].browse(concept['contract_id'])
            raw_data = {
                'document': contract.employee_id.identification_id,
                'name': contract.employee_id.partner_id.name,
                'charge': contract.job_id.name,
                'cecos': contract.cecos_analytic_id.name or '',
                'cecos_ref': contract.cecos_analytic_id.code or '',
                'contract_group': contract.contract_group_id.name or '',
                'wage': contract.wage,
            }

            # Earnings
            for line in self.template_id.earning_lines_ids:
                safe_alias = self._safe_alias(line.alias)
                if safe_alias in concept.keys():
                    alias = line.alias
                    safe_alias_qty = safe_alias + '_qty'
                    is_apprentice_line = line.sen_ele or line.sen_prod
                    if line.is_basic and (contract.contract_type_id.type_class == 'int' or contract.fiscal_type_id.code == '12' or contract.fiscal_type_id.code == '19') and not line.int and not is_apprentice_line:
                        raw_data[alias] = {'amount': 0.0, 'qty': 0.0}
                        continue
                    if line.is_basic and line.int and not contract.contract_type_id.type_class == 'int':
                        raw_data[alias] = {'amount': 0.0, 'qty': 0.0}
                        continue
                    elif line.is_basic and is_apprentice_line:
                        apprentice_codes = []
                        if line.sen_ele:
                            apprentice_codes.append('12')
                        if line.sen_prod:
                            apprentice_codes.append('19')
                        if contract.fiscal_type_id.code not in apprentice_codes:
                            raw_data[alias] = {'amount': 0.0, 'qty': 0.0}
                            continue
                    raw_data[alias] = {'amount': concept.get(safe_alias, 0.0), 'qty': concept.get(safe_alias_qty, 0.0)}
                    total_earnings += concept.get(safe_alias, 0.0)
            raw_data['total_earnings'] = total_earnings
            # Deductions
            for line in self.template_id.deduction_lines_ids:
                safe_alias = self._safe_alias(line.alias)
                if safe_alias in concept.keys():
                    alias = line.alias
                    safe_alias_qty = safe_alias + '_qty'
                    raw_data[alias] = {'amount': concept.get(safe_alias, 0.0), 'qty': concept.get(safe_alias_qty, 0.0)}
                    total_deductions += concept.get(safe_alias, 0.0)
            raw_data['total_deductions'] = total_deductions
            # Nets
            for line in self.template_id.net_lines_ids:
                safe_alias = self._safe_alias(line.alias)
                if safe_alias in concept.keys():
                    alias = line.alias
                    safe_alias_qty = safe_alias + '_qty'
                    raw_data[alias] = {'amount': concept.get(safe_alias, 0.0), 'qty': concept.get(safe_alias_qty, 0.0)}
            data.append(raw_data)
        return data

    def _get_amount_by_category(self, concept, category):
        return {'amount': concept.get(category, 0.0), 'qty': concept.get(category + '_qty', 0.0)}

    def get_concepts(self, date_from, date_to, contracts_ids, payslip_type_ids, template):
        subquerys = []
        for line in template.earning_lines_ids:
            subquerys.append(
                self.build_subquerys(line.alias, line.concepts_ids.ids)
            )
        for line in template.deduction_lines_ids:
            subquerys.append(
                self.build_subquerys(line.alias, line.concepts_ids.ids)
            )
        for line in template.net_lines_ids:
            subquerys.append(
                self.build_subquerys(line.alias, line.concepts_ids.ids)
            )

        if all(not subquery for subquery in subquerys):
            raise ValidationError(
                'No se han configurados los conceptos de la plantilla')

        subtotals_query = []
        fields_query = []
        for subquery in filter(lambda sq: sq, subquerys):
            subtotals_query.append(subquery['subtotal_query'])
            fields_query.append(subquery['field_query'])
        state_query = "HP.state = '{state}' AND".format(state=self.payslip_state) if self.payslip_state else ""

        query = f'''
        WITH 
            payslips AS (
                SELECT HP.id, HP.contract_id
                FROM hr_payslip AS HP
                INNER JOIN hr_period AS PP
                    ON PP.id = HP.period_id
                WHERE 
                    HP.contract_id IN %(contracts_ids)s AND
                    HP.payslip_type_id IN %(payslip_type_ids)s AND
                    {state_query}
                    PP.start <= %(date_to)s AND PP.end >= %(date_from)s

            ),
            contracts AS (
                SELECT contract_id AS id FROM payslips GROUP BY contract_id
            ),
            {','.join(subtotals_query)}
        SELECT 
            id AS contract_id,
            {','.join(fields_query)}
        FROM contracts;
        '''

        params = {
            'contracts_ids': contracts_ids,
            'payslip_type_ids': payslip_type_ids,
            'date_from': date_from,
            'date_to': date_to
        }
        self._cr.execute(query, params)
        return self._cr.dictfetchall()

    @staticmethod
    def _safe_alias(alias):
        return re.sub(r'[^a-zA-Z0-9_]', '_', alias)

    def build_subquerys(self, alias, concepts_ids):
        if not concepts_ids:
            return {}
        safe = self._safe_alias(alias)
        if len(concepts_ids) == 1:
            concepts_ids.append(0)
        subtotal_query = f'''
            {safe} AS (
                SELECT
                    HP.contract_id,
                    COALESCE(SUM(HPL.total), 0) AS total,
                    COALESCE(SUM(HPL.qty), 0) AS qty
                FROM hr_payslip_line AS HPL
                INNER JOIN payslips AS HP
                    ON HP.id = HPL.payslip_id
                INNER JOIN (
                    SELECT name FROM income_and_withholding_concepts
                    WHERE id IN {tuple(concepts_ids)}
                ) AS IWC
                    ON IWC.name = HPL.name
                GROUP BY HP.contract_id
            )
        '''
        field_query = f"COALESCE((SELECT total FROM {safe} WHERE contract_id = id), 0) AS {safe}, COALESCE((SELECT qty FROM {safe} WHERE contract_id = id), 0) AS {safe}_qty"
        return {
            'subtotal_query': subtotal_query,
            'field_query': field_query
        }

    def _get_colums(self, template, line_type):
        if line_type == 'earning':
            lines = template.earning_lines_ids
        elif line_type == 'deduction':
            lines = template.deduction_lines_ids
        else:
            lines = template.net_lines_ids
        return lines
