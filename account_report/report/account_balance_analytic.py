# -*- coding: utf-8 -*-

from odoo import _, fields, models

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF',
}


class ReportBalanceAnalytic(models.AbstractModel):
    _name = 'report.account_report.account_balance_analytic'
    _description = 'Cost Center Balance Report'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        format_border = workbook.add_format({'border': True})
        format_bold = workbook.add_format({'border': True, 'bold': True})
        format_old = workbook.add_format({'bold': True})
        format_color = workbook.add_format(
            {'border': True, 'bold': True, 'bg_color': '#ADD8E6'})
        format_num = workbook.add_format(
            {'border': True, 'num_format': '#,##0.00'})
        format_number = workbook.add_format(
            {'border': True, 'bold': True, 'num_format': '#,##0.00'})
        format_date = workbook.add_format({'num_format': 'dd-mm-yy'})
        format_right = workbook.add_format({'align': 'right'})

        worksheet = workbook.add_worksheet()

        date_process = fields.Datetime.context_timestamp(
            self, objs.date_process).strftime('%Y/%m/%d %H:%M:%S')

        # Encabezado informativo
        worksheet.write(0, 0, 'INFORME', format_old)
        worksheet.write(0, 1, 'BALANCE CENTROS DE COSTOS')
        worksheet.write(1, 0, 'TIPO', format_old)
        worksheet.write(1, 1, REPORT_TYPE.get(objs.report_type))
        worksheet.write(2, 0, 'COMPAÑÍA', format_old)
        worksheet.write(2, 1, self.env.company.name)
        worksheet.write(3, 0, 'NIT', format_old)
        worksheet.write(3, 1, self.env.company.vat or '')
        worksheet.write(0, 4, 'FECHA PROCESO', format_old)
        worksheet.write(0, 5, date_process, format_right)
        worksheet.write(1, 4, 'DESDE', format_old)
        worksheet.write(
            1, 5, objs.date_from.strftime('%Y/%m/%d'), format_date)
        worksheet.write(2, 4, 'HASTA', format_old)
        worksheet.write(
            2, 5, objs.date_to.strftime('%Y/%m/%d'), format_date)

        # Encabezados de columna
        report_header = objs.prepare_header()
        for i, (_, label) in enumerate(report_header):
            worksheet.write(5, i, str(label).upper(), format_color)

        # Datos
        report_data = data.get('report_data', [])
        amount_keys = ('initial', 'debit', 'credit', 'final')
        cw = {}

        for i, row in enumerate(report_data):
            is_bold = row.get('bold')
            for col, (key, _) in enumerate(report_header):
                value = row.get(key, '')
                cw[col] = cw.get(col, []) + [len(str(value))]
                if key in amount_keys:
                    fmt = format_number if is_bold else format_num
                    worksheet.write(i + 6, col, value or 0, fmt)
                else:
                    fmt = format_bold if is_bold else format_border
                    worksheet.write(i + 6, col, value or '', fmt)

        # Ajustar ancho de columnas
        for col_idx, widths in cw.items():
            worksheet.set_column(col_idx, col_idx, max(widths) + 4)
