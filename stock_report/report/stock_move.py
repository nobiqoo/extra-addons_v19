# -*- coding: utf-8 -*-

from odoo import models


class ReportStockMove(models.AbstractModel):
    _name = 'report.stock_report.report_stock_move'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Stock move report'

    def generate_xlsx_report(self, workbook, data, objs):
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '$#,##0.00'})
        num = workbook.add_format({'num_format': '#,##0.00'})

        worksheet_info = workbook.add_worksheet('Información')
        worksheet_info.write('A1', 'Compañia', bold)
        worksheet_info.write('B1', data.get('company'))
        worksheet_info.write('A2', 'Usuario', bold)
        worksheet_info.write('B2', data.get('user'))
        worksheet_info.write('A3', 'Desde', bold)
        worksheet_info.write('B3', data.get('start'))
        worksheet_info.write('A4', 'Hasta', bold)
        worksheet_info.write('B4', data.get('end'))

        locations = data.get('locations')
        for location in locations:
            worksheet = workbook.add_worksheet(location.get('name'))
            worksheet.write('A1', 'Fecha', bold)
            worksheet.write('B1', 'Referencia', bold)
            worksheet.write('C1', 'Origen', bold)
            worksheet.write('D1', 'Tercero', bold)
            worksheet.write('E1', 'Producto', bold)
            worksheet.write('F1', 'Desde', bold)
            worksheet.write('G1', 'A', bold)
            worksheet.write('H1', 'Tipo', bold)
            worksheet.write('I1', 'C. Inicial', bold)
            worksheet.write('J1', 'Cantidad', bold)
            worksheet.write('K1', 'C. Final', bold)
            worksheet.write('L1', 'UdM', bold)
            # worksheet.write('M1', 'P. Unitario', bold)
            # worksheet.write('N1', 'P. Total', bold)

            products = location.get('products')
            row = 2
            for product in products:
                for move in product.get('moves'):
                    worksheet.write('A%s' % row, move.get('date'))
                    worksheet.write('B%s' % row, move.get('reference'))
                    worksheet.write('C%s' % row, move.get('origin'))
                    worksheet.write('D%s' % row, move.get('partner'))
                    worksheet.write('E%s' % row, move.get('product'))
                    worksheet.write('F%s' % row, move.get('from'))
                    worksheet.write('G%s' % row, move.get('to'))
                    worksheet.write('H%s' % row, move.get('type'))
                    worksheet.write('I%s' % row, move.get('init'), num)
                    worksheet.write('J%s' % row, move.get('demand'), num)
                    worksheet.write('K%s' % row, move.get('final'), num)
                    worksheet.write('L%s' % row, move.get('uom'))
                    # worksheet.write('M%s' % row, move.get('unit'), money)
                    # worksheet.write('N%s' % row, move.get('total'), money)
                    row += 1
