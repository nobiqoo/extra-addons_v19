from odoo import api, fields, models, _
import xlsxwriter
from io import BytesIO
from datetime import date
import base64

class PortfolioDetailPrintXlsx(models.TransientModel):
    _name = 'portfolio.detail.print.xlsx'
    _description = 'Portfolio Detail Print Xlsx'

    report_id = fields.Many2one(
        comodel_name='portfolio.detail.wizard',
        string='Report',
        required=True,
    )
    file_binary = fields.Binary(
        string='File'
    )
    file_name = fields.Char(
        string='File name'
    )

    def _get_file_name(self):
        return _('portfolio_detail') + '_' + str(date.today()).replace('-','_')

    def _get_move_header(self):
        res = {
            0: {'header': _('Invoice'), 'format': 'detail', 'field': 'product', 'width': 40},
            1: {'header': _('Partner'), 'format': 'detail', 'field': 'type_line', 'width': 20},
            2: {'header': _('NIT'), 'format': 'detail', 'field': 'payment_state', 'width': 15},
            3: {'header': _('Invoice Date'), 'format': 'detail', 'field': 'move_tag', 'width': 20},
            4: {'header': _('Date due'), 'format': 'detail', 'field': 'payment_date', 'width': 20},
            5: {'header': _('Amount untaxed'), 'format': 'num_format', 'field': 'customer', 'width': 40},
            6: {'header': _('Amount total'), 'format': 'num_format', 'field': 'base_commission', 'width': 20},
        }
        return res

    def _define_formats(self, workbook):
        # format for worksheet title
        formats = {}
        formats["title_cell"] = workbook.add_format({
            'font_size': 12,
            'align': 'center',
            'bold': True,
            'border': 1
        })
        formats["column_title_cell"] = workbook.add_format({
            'font_size': 10,
            'align': 'center',
            'bold': True,
            'border': 1
        })
        formats["num_format"] = workbook.add_format({
            'font_size': 10,
            'bold': False,
            'border': 1,
            'num_format': '$#,##0.00'
        })
        formats["num_strong"] = workbook.add_format({
            'font_size': 10,
            'bold': True,
            'border': 1,
            'num_format': '$#,##0.00'
        })
        formats["detail"] = workbook.add_format({
            'font_size': 10,
            'bold': False,
            'border': 1
        })
        return formats

    def _group_detail_lines(self):
        list_lines = []
        for line in self.report_id.line_ids:
            list_lines.append([
                line.invoice,
                line.partner,
                line.nit,
                str(line.invoice_date),
                str(line.due_date),
                line.amount_untaxed,
                line.amount_total,
                line.line_ids
            ])
        return list_lines

    def print_move_header(self, sheet, row, col, formats):
        headers = self._get_move_header()
        sheet.merge_range(row, 1, row, len(headers.items())-1, _('Portfolio Detail'),formats['title_cell'])
        row += 1
        sheet.write(row, 1, _('Date from'), formats['column_title_cell'])
        sheet.write(row, 2, str(self.report_id.date_from), formats['detail'])
        sheet.write(row, 3, _('Date to'), formats['column_title_cell'])
        sheet.write(row, 4, str(self.report_id.date_to), formats['detail'])
        row += 1
        sheet.write(row, 1, _('Partners Involved'), formats['column_title_cell'])
        sheet.write(row, 2, str(self.report_id.partners_involved), formats['detail'])
        row += 1
        for column, values in headers.items():
            sheet.set_column(column, column, values.get('width'))
            sheet.write(row, column, values.get(
                'header'), formats['column_title_cell'])
        column += 1
        sheet.set_column(column, column, values.get('width'))
        sheet.write(row, column, _('Voucher name'), formats['column_title_cell'])
        column += 1
        sheet.set_column(column, column, values.get('width'))
        sheet.write(row, column, _('Reference'), formats['column_title_cell'])
        column += 1
        sheet.set_column(column, column, values.get('width'))
        sheet.write(row, column, _('Payment date'), formats['column_title_cell'])
        column += 1
        sheet.set_column(column, column, values.get('width'))
        sheet.write(row, column, _('Payment method'), formats['column_title_cell'])
        column += 1
        sheet.set_column(column, column, values.get('width'))
        sheet.write(row, column, _('Amount'), formats['column_title_cell'])
        column += 1
        sheet.set_column(column, column, values.get('width'))
        sheet.write(row, column, _('Pending amount'), formats['column_title_cell'])
        row += 1
        return row, col

    def print_move_detail(self, sheet, value, row, col, formats):
        headers = self._get_move_header()
        for column in headers.keys():
            if headers[column]['format'] == 'num_format':
                value_amount = float(value[column])
            else: 
                value_amount = value[column]
            sheet.write(row, column, value_amount, formats[headers[column]['format']])
        row += 1
        return row, column

    def print_move_line_detail(self, sheet, row, col, formats):
        list_lines = self._group_detail_lines()
        detail_lines = []
        extra_lines = []
        for list_line in list_lines:
            detail_lines.append(list_line[:7])
            extra_lines.append(list_line[7])
        for i, value in enumerate(detail_lines):
            row, col = self.print_move_detail(
                sheet, value, row, col, formats)
            col += 1
            for line in extra_lines[i]:
                sheet.write(row, col, line.name, formats['detail'])
                sheet.write(row, col + 1, str(line.date), formats['detail'])
                sheet.write(row, col + 2, line.ref, formats['detail'])
                sheet.write(row, col + 3, line.payment_method, formats['detail'])
                sheet.write(row, col + 4, line.amount_paid, formats['num_format'])
                sheet.write(row, col + 5, line.pending_amount, formats['num_format'])
                row += 1
        return row, col
 
    def print_total_commissions(self, sheet, row, formats):
        headers = self._get_move_header()
        sheet.write(row, len(headers.keys()) - 2, _("SUBTOTAL:"), formats['column_title_cell'])
        sheet.write(row, len(headers.keys()) - 1, self.report_id.subtotal_amount, formats['num_strong'])
        row += 1
        sheet.write(row, len(headers.keys()) - 2, _("Salary adjustment:"), formats['column_title_cell'])
        sheet.write(row, len(headers.keys()) - 1, self.report_id.salary_adjustment, formats['num_strong'])
        row += 1
        sheet.write(row, len(headers.keys()) - 2, _("Paid percentaje:"), formats['column_title_cell'])
        sheet.write(row, len(headers.keys()) - 1, self.report_id.paid_percentage, formats['num_strong'])
        row += 1
        sheet.write(row, len(headers.keys()) - 2, _("Total:"), formats['column_title_cell'])
        sheet.write(row, len(headers.keys()) - 1, self.report_id.total_amount, formats['num_strong'])
        row += 1
        return row

    def create_xlsx_file(self):
        self.file_name = self._get_file_name()
        output = BytesIO()
        formats = {}
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False
        })
        row, col = 0, 0
        sheet = workbook.add_worksheet(_('portfolio_detail'))
        # Define Formats XLSX
        formats = self._define_formats(workbook)
        row, col = self.print_move_header(sheet, row, col, formats)
        row, col = self.print_move_line_detail(sheet, row, col, formats)
        # row = self.print_total_commissions(sheet, row, formats)
        workbook.close()
       
        report_data = output.getvalue()
        self.file_binary = base64.b64encode(report_data)
        return {
            'name': _('Download File'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'portfolio.detail.print.xlsx',
            'res_id': self.id,
            'target': 'new',
        }