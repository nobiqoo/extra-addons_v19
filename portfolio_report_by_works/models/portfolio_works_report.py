# -*- coding: utf-8 -*-
from odoo import _, fields, models
from datetime import date
from io import BytesIO
import xlsxwriter
import base64

class PortfolioWorksReport(models.TransientModel):
    _name = "portfolio.works.report"
    _description = "Portfolio works report"

    customer_ids = fields.Many2many('res.partner', string="Cutomers")
    cut_date = fields.Date(string='Cut date', required=True, help="Invoices up to this date will be consulted.")
    work_ids = fields.Many2many('sale.order.work', string="Works", help="Fill only if you like apply the filter, else leave void.")
    file_binary = fields.Binary(
        string='File'
    )
    file_name = fields.Char(
        string='File name'
    )

    def get_report_data(self):
        tuple_customer_ids = tuple(self.customer_ids.ids)
        tuple_work_ids = tuple(self.work_ids) if len(self.work_ids) > 0 else ()
        query = """
            select rp.name as partner,
            rp.vat as partner_vat,
            sow.name as work_name,
            am.name as move_name,
            am.invoice_date as move_date,
            am.invoice_date_due as move_date_due,
            am.amount_total as amount_total,
            ('{cut_date}' - am.invoice_date_due) as due_days,
            am.amount_residual as residual_amount,
            rp2.name as seller
            from account_move am
                inner join res_partner rp on rp.id = am.partner_id
                inner join sale_order_work sow on sow.id = am.work_id
                inner join res_users ru on ru.id = am.invoice_user_id
                inner join res_partner rp2 on rp2.id = ru.partner_id
            where am.invoice_date <= '{cut_date}' and
                am.move_type = 'out_invoice' and
                am.partner_id in {tuple_customer_ids}
        """.format(
                cut_date=self.cut_date,
                tuple_customer_ids=tuple_customer_ids
            )
        if len(tuple_work_ids) > 0:
            query += " and am.work_id in %s" % (tuple_work_ids)
        self._cr.execute(query)
        report_data = self._cr.dictfetchall()
        return report_data

    def create_report(self):
        portfolio_print = self.env['portfolio.works.report.xlsx'].create({ 
            'report_id' : self.id 
        })
        return portfolio_print.create_xlsx_file()


    def _get_file_name(self):
        return _('portfolio_detail') + '_' + str(date.today()).replace('-','_')

    def _get_move_header(self):
        res = {
            0: {'header': _('Customer'), 'format': 'detail', 'field': 'customer', 'width': 40},
            1: {'header': _('NIT'), 'format': 'detail', 'field': 'nit', 'width': 20},
            2: {'header': _('Work'), 'format': 'detail', 'field': 'work', 'width': 15},
            3: {'header': _('Number'), 'format': 'detail', 'field': 'number', 'width': 20},
            4: {'header': _('Invoice date'), 'format': 'detail', 'field': 'invoice_date', 'width': 20},
            5: {'header': _('Due date'), 'format': 'detail', 'field': 'customer', 'due_date': 20},
            6: {'header': _('Due days'), 'format': 'num_format', 'field': 'due_days', 'width': 20},
            7: {'header': _('Amount residual'), 'format': 'num_format', 'field': 'amount_residual', 'width': 20},
            8: {'header': _('Seller'), 'format': 'detail', 'field': 'seller', 'width': 20},
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
        report_data = self.get_report_data()
        list_lines = []
        for line in report_data:
            list_lines.append([
                line['partner'],
                line['partner_vat'],
                line['work_name'],
                line['move_name'],
                line['move_date'],
                line['move_date_due'],
                line['amount_total'],
                line['due_days'],
                line['residual_amount'],
                line['seller']

            ])
        return list_lines

    def print_move_header(self, sheet, row, col, formats):
        headers = self._get_move_header()
        sheet.merge_range(row, 1, row, len(headers.items())-1, _('Portfolio Detail'),formats['title_cell'])
        row += 1
        sheet.write(row, 1, _('Cut Date'), formats['column_title_cell'])
        sheet.write(row, 2, str(self.cut_date), formats['detail'])
        # row += 1
        # sheet.write(row, 1, _('Partners Involved'), formats['column_title_cell'])
        # sheet.write(row, 2, str(self.report_id.partners_involved), formats['detail'])
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
        for list_line in list_lines:
            col += 1
            sheet.write(row, col, list_line[0], formats['detail'])
            sheet.write(row, col + 1, list_line[1], formats['detail'])
            sheet.write(row, col + 2, list_line[2], formats['detail'])
            sheet.write(row, col + 3, list_line[3], formats['detail'])
            sheet.write(row, col + 4, list_line[4], formats['num_format'])
            sheet.write(row, col + 5, list_line[5], formats['num_format'])
            sheet.write(row, col + 5, list_line[6], formats['num_format'])
            sheet.write(row, col + 5, list_line[7], formats['num_format'])
            sheet.write(row, col + 5, list_line[8], formats['num_format'])
            sheet.write(row, col + 5, list_line[9], formats['num_format'])
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
            'res_model': 'portfolio.works.report',
            'res_id': self.id,
            'target': 'new',
        }