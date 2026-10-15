# -*- coding: utf-8 -*-
from odoo import models


class ReportAccountAnalytic(models.AbstractModel):
    _name = 'report.account_logistic_odone.report_account_analytic'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Account analytic report'

    def generate_xlsx_report(self, workbook, data, objs):

        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '$#,##0'})

        accounts = data.get('account_ids')
        for account in accounts:
            worksheet = workbook.add_worksheet(account.get('name'))

            company = self.env.company.currency_id
            account_name = '%s - %s' % (account.get('name'), company.name)
            name_a1 = 'Analisis resumido de la posición %s' % account_name
            worksheet.merge_range('A1:I1', name_a1, bold)

            worksheet.write('A3', 'Origen', bold)
            worksheet.write('B3', account.get('origin'), bold)
            worksheet.write('A4', 'Destino', bold)
            worksheet.write('B4', account.get('destination'), bold)
            worksheet.write('A5', 'Motonave', bold)
            worksheet.write('B5', account.get('motor'), bold)
            worksheet.write('A7', 'Tipo', bold)
            worksheet.write('B7', 'Documento', bold)
            worksheet.write('C7', 'Fecha', bold)
            worksheet.write('D7', 'Tercero', bold)
            worksheet.write('E7', 'Ingresos', bold)
            worksheet.write('F7', 'Egresos', bold)
            worksheet.write('G7', 'Detalle', bold)
            worksheet.write('H7', 'Moneda', bold)
            worksheet.write('I7', 'TRM', bold)

            row = 8
            for line in account.get('line_ids'):
                amount = line.get('amount')
                debit = amount > 0 and amount or 0.0
                credit = amount < 0 and -amount or 0.0
                worksheet.write('A%s' % row, 'FAC.')
                worksheet.write('B%s' % row, line.get('move'))
                worksheet.write('C%s' % row, line.get('date'))
                worksheet.write('D%s' % row, line.get('partner'))
                worksheet.write('E%s' % row, debit, money)
                worksheet.write('F%s' % row, credit, money)
                worksheet.write('G%s' % row, line.get('name'))
                worksheet.write('H%s' % row, line.get('currency'))
                worksheet.write('I%s' % row, line.get('rate'))
                row += 1

            worksheet.write('D%s' % row, 'Total', bold)
            worksheet.write('E%s' % row, '=SUM(E8:E%s)' % str(row-1), money)
            worksheet.write('F%s' % row, '=SUM(F8:F%s)' % str(row-1), money)
            worksheet.write('D%s' % str(row+1), 'Rentabilidad', bold)
            worksheet.write('E%s' % str(row+1), '=E%s-F%s' % (row, row), money)
