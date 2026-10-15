# -*- coding: utf-8 -*-

from odoo import models


class ReportPygAnalyticPositionReport(models.AbstractModel):
    _name = 'report.account_pyg.pyg_analytic_position_report'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Informe de Comisiones XLSX'

    def generate_xlsx_report(self, workbook, data, objs):
        bold = workbook.add_format({'bold': True, 'valign': 'vcenter'})
        money = workbook.add_format({
            'num_format': '_-[$$-es-CO] * #,##0.00_-;-[$$-es-CO] * #,##0.00_-',
            'valign': 'vcenter',
        })
        cell = workbook.add_format({'valign': 'vcenter'})
        large_text = workbook.add_format({'valign': 'vcenter', 'text_wrap': True})
        money_total = workbook.add_format({
            'bold': True,
            'valign': 'vcenter',
            'num_format': '_-[$$-es-CO] * #,##0.00_-;-[$$-es-CO] * #,##0.00_-',
        })

        accounts = data.get('account_ids')
        for account in accounts:
            worksheet = workbook.add_worksheet(account.get('name'))
            worksheet.set_column('A:B', 15, cell)
            worksheet.set_column('C:C', 10, cell)
            worksheet.set_column('D:D', 30, large_text)
            worksheet.set_column('E:I', 18, cell)
            worksheet.set_column('J:J', 5, cell)
            worksheet.set_column('K:K', 10, cell)
            worksheet.set_column('L:L', 60, large_text)
            worksheet.set_column('M:O', 30, large_text)
            worksheet.set_column('P:P', 10, cell)
            worksheet.set_column('Q:Q', 50, large_text)
            worksheet.set_column('R:T', 15, cell)
            worksheet.set_column('U:U', 30, large_text)

            currency_id = self.env.company.currency_id
            account_name = '%s - %s' % (account.get('name'), currency_id.name)
            name_a1 = 'Analisis resumido de la posición: %s' % account_name
            worksheet.merge_range('A1:I1', name_a1, bold)

            worksheet.write('A7', 'Tipo', bold)
            worksheet.write('B7', 'Documento', bold)
            worksheet.write('C7', 'Fecha', bold)
            worksheet.write('D7', 'Tercero', bold)
            worksheet.write('E7', 'Ingresos', bold)
            worksheet.write('F7', 'Egresos', bold)
            worksheet.write('G7', 'Rentabilidad', bold)
            worksheet.write('H7', 'Rentabilidad (USD)', bold)
            worksheet.write('I7', 'Rentabilidad (Doc)', bold)
            worksheet.write('J7', 'Moneda', bold)
            worksheet.write('K7', 'TRM', bold)
            worksheet.write('L7', 'Detalle', bold)
            worksheet.write('M7', 'Origen', bold)
            worksheet.write('N7', 'Destino', bold)
            worksheet.write('O7', 'Motonave', bold)
            worksheet.write('P7', 'Peso', bold)
            worksheet.write('Q7', 'Posición', bold)
            worksheet.write('R7', 'HBL', bold)
            worksheet.write('S7', 'Volumen', bold)
            worksheet.write('T7', 'ETA', bold)
            worksheet.write('U7', 'Vendedor', bold)

            row = 8
            for line in account.get('line_ids'):
                worksheet.write('A%s' % row, line.get('type_doc'))
                worksheet.write('B%s' % row, line.get('move'))
                worksheet.write('C%s' % row, line.get('date'))
                worksheet.write('D%s' % row, line.get('partner'))
                worksheet.write('E%s' % row, line.get('profit'), money)
                worksheet.write('F%s' % row, line.get('loss'), money)
                worksheet.write('G%s' % row, line.get('profitability'), money)
                worksheet.write('H%s' % row, line.get('profitability_usd'), money)
                worksheet.write('I%s' % row, line.get('profitability_doc'), money)
                worksheet.write('J%s' % row, line.get('currency'))
                worksheet.write('K%s' % row, line.get('rate'))
                worksheet.write('L%s' % row, line.get('detail'))
                worksheet.write('M%s' % row, line.get('origin'))
                worksheet.write('N%s' % row, line.get('destination'))
                worksheet.write('O%s' % row, line.get('motor'))
                worksheet.write('P%s' % row, line.get('weight'))
                worksheet.write('Q%s' % row, line.get('position'))
                worksheet.write('R%s' % row, line.get('hbl'))
                worksheet.write('S%s' % row, line.get('volume'))
                worksheet.write('T%s' % row, line.get('eta'))
                worksheet.write('U%s' % row, line.get('salesman'))
                row += 1

            worksheet.write('D%s' % row, 'Total', bold)
            worksheet.write('E%s' % row, '=SUM(E8:E%s)' % str(row - 1), money_total)
            worksheet.write('F%s' % row, '=SUM(F8:F%s)' % str(row - 1), money_total)
            worksheet.write('G%s' % row, '=SUM(G8:G%s)' % str(row - 1), money_total)
            worksheet.write('H%s' % row, '=SUM(H8:H%s)' % str(row - 1), money_total)
            worksheet.write('I%s' % row, '=SUM(I8:I%s)' % str(row - 1), money_total)
