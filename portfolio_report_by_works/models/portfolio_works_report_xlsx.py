# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import xlsxwriter
from io import BytesIO
from datetime import date
import base64

class PortfolioWorksReportXlsx(models.TransientModel):
    _name = 'portfolio.works.report.xlsx'
    _description = 'Portfolio works report xlsx'

    report_id = fields.Many2one(
        comodel_name='portfolio.works.report',
        string='Report',
        required=True,
    )
    file_binary = fields.Binary(
        string='File'
    )
    file_name = fields.Char(
        string='File name'
    )

    def get_report_data(self):
        tuple_customer_ids = tuple(self.report_id.customer_ids.ids)
        tuple_work_ids = tuple(self.report_id.work_ids.ids) if len(self.report_id.work_ids) > 0 else ()
        query = """
            select rp.name as partner,
            rp.vat as partner_vat,
            sow.name as work_name,
            am.name as move_name,
            am.invoice_date as move_date,
            am.invoice_date_due as move_date_due,
            am.amount_total as amount_invoice,
            0 as amount_total,
            ('{cut_date}' - am.invoice_date) as due_days,
            am.amount_residual as residual_amount,
            0 as total_residual,
            rp2.name as seller,
            'regular' as cell_format
            from account_move am
                inner join res_partner rp on rp.id = am.partner_id
                inner join sale_order_work sow on sow.id = am.work_id
                inner join res_users ru on ru.id = am.invoice_user_id
                inner join res_partner rp2 on rp2.id = ru.partner_id
            where am.invoice_date <= '{cut_date}' and
                am.move_type = 'out_invoice' and
                am.amount_residual > 0 and
                am.state = 'posted'

        """.format(
                cut_date=self.report_id.cut_date
            )
        if len(tuple_customer_ids) > 0:
            str_tuple_customer_ids = str(tuple_customer_ids) if len(tuple_customer_ids) > 1 else '(' + str(tuple_customer_ids[0]) + ')'
            query += " and am.partner_id in %s" % (str_tuple_customer_ids)
        if len(tuple_work_ids) > 0:
            str_tuple_work_ids = str(tuple_work_ids) if len(tuple_work_ids) > 1 else '(' + str(tuple_work_ids[0]) + ')'
            query += " and am.work_id in %s" % (str_tuple_work_ids)
        query += " order by rp.name, am.invoice_date_due asc"
        self._cr.execute(query)
        report_data = self._cr.dictfetchall()
        return report_data

    def create_report(self):
        return self.create_xlsx_file()

    def _get_file_name(self):
        return _('portfolio_detail') + '_' + str(date.today()).replace('-','_')

    def _get_move_header(self):
        res = {
            0: {'header': _('Customer'), 'format': 'detail', 'width': 40},
            1: {'header': _('NIT'), 'format': 'detail', 'width': 20},
            2: {'header': _('Work'), 'format': 'detail', 'width': 20},
            3: {'header': _('Number'), 'format': 'detail', 'width': 20},
            4: {'header': _('Invoice date'), 'format': 'detail', 'width': 20},
            5: {'header': _('Due date'), 'format': 'detail', 'width': 20},
            6: {'header': _('Due days'), 'format': 'num_format', 'width': 20},
            7: {'header': _('Invoice amount'), 'format': 'num_format', 'width': 20},
            8: {'header': _('Total amount'), 'format': 'num_format', 'width': 20},
            9: {'header': _('Amount residual'), 'format': 'num_format', 'width': 20},
            10: {'header': _('Total residual'), 'format': 'num_format', 'width': 20},
            11: {'header': _('Seller'), 'format': 'detail', 'width': 25},
        }
        return res

    def _define_formats(self, workbook):
        # format for worksheet title
        formats = {}
        formats["title_cell"] = workbook.add_format({
            'font_size': 14,
            'align': 'center',
            'bold': True,
            'border': 1,
            'italic': True
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
        formats["total_work"] = workbook.add_format({
            'font_size': 10,
            'bg_color': '#FFFF00',
            'bold': True,
            'border': 1,
            'num_format': '$#,##0.00'
        })
        formats["total_customer"] = workbook.add_format({
            'font_size': 10,
            'bg_color': '#FF8000',
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
            due_days = 0
            if int(line['due_days']) > 0:
                due_days = int(line['due_days']) -1
            else:
                due_days = int(line['due_days'])
            list_lines.append([
                line['partner'],
                line['partner_vat'],
                line['work_name'],
                line['move_name'],
                str(line['move_date']),
                str(line['move_date_due']),
                due_days,
                line['amount_invoice'],
                line['amount_total'],
                line['residual_amount'],
                line['total_residual'],
                line['seller'],
                line['cell_format']
            ])
        return list_lines

    def print_move_header(self, sheet, row, col, formats):
        headers = self._get_move_header()
        sheet.merge_range(row, 1, row, len(headers.items())-1, _('Portfolio Detail'),formats['title_cell'])
        row += 1
        sheet.write(row, 1, _('Cut Date'), formats['column_title_cell'])
        sheet.write(row, 2, str(self.report_id.cut_date), formats['detail'])
        row += 1
        for column, values in headers.items():
            sheet.set_column(column, column, values.get('width'))
            sheet.write(row, column, values.get(
                'header'), formats['column_title_cell'])
        row += 1
        return row, col

    def group_by_work_detail_lines(self, list_lines):
        works_list = []
        customers_list = []
        for line in list_lines:
            if line[2] not in works_list:
                works_list.append(line[2])
            if line[0] not in customers_list:
                customers_list.append(line[0])
        customers_grouped_list = []
        for cutomer_line in customers_list:
            grouped_list = []
            for line in list_lines:
                if cutomer_line == line[0]:
                    if len(grouped_list) == 0:
                        grouped_list.append(line)
                    else:
                        line[0] = ''
                        line[1] = ''
                        grouped_list.append(line)
            customers_grouped_list.append(grouped_list)
        new_list = []
        for cutomer_group in customers_grouped_list:
            total_customer_amount_total = 0
            total_customer_due_days = 0
            total_customer_residual_amount = 0
            for work_line in works_list:
                total_amount_total = 0
                total_due_days = 0
                total_residual_amount = 0
                work_found = False
                for line in cutomer_group:
                    if line[2] == work_line:
                        total_amount_total += line[7]
                        total_due_days += line[6]
                        total_residual_amount += line[9]
                        if work_found:
                            line[2] = ''
                        new_list.append(line)
                        work_found = True
                if work_found:
                    new_list.append([
                        line[0],
                        '',
                        '',
                        '',
                        '',
                        '',
                        total_due_days,
                        total_amount_total,
                        0,
                        total_residual_amount,
                        0,
                        '',
                        'work'
                    ])
                    total_customer_amount_total += total_amount_total
                    total_customer_due_days += total_due_days
                    total_customer_residual_amount += total_residual_amount
            new_list.append([
                '',
                '',
                '',
                '',
                '',
                '',
                total_customer_due_days,
                0,
                total_customer_amount_total,
                0,
                total_customer_residual_amount,
                '',
                'customer'
            ])
        return new_list

    def print_move_line_detail(self, sheet, row, col, formats):
        list_lines = self._group_detail_lines()
        list_lines = self.group_by_work_detail_lines(list_lines)
        for list_line in list_lines:
            col = 0
            sheet.write(row, col, list_line[0], formats['detail'])
            sheet.write(row, col + 1, list_line[1], formats['detail'])
            sheet.write(row, col + 2, list_line[2], formats['detail'])
            sheet.write(row, col + 3, list_line[3], formats['detail'])
            sheet.write(row, col + 4, list_line[4], formats['detail'])
            sheet.write(row, col + 5, list_line[5], formats['detail'])
            sheet.write(row, col + 6, list_line[6] if list_line[12] == 'regular' else '', formats['detail'])
            sheet.write(row, col + 7, list_line[7], formats['total_work'] if list_line[12] == 'work' else formats['num_format'])
            sheet.write(row, col + 8, list_line[8], formats['total_customer'] if list_line[12] == 'customer' else formats['num_format'])
            sheet.write(row, col + 9, list_line[9], formats['total_work'] if list_line[12] == 'work' else formats['num_format'])
            sheet.write(row, col + 10, list_line[10], formats['total_customer'] if list_line[12] == 'customer' else formats['num_format'])
            sheet.write(row, col + 11, list_line[11], formats['detail'])
            row += 1
        return row, col
 
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
        workbook.close()
       
        report_data = output.getvalue()
        self.file_binary = base64.b64encode(report_data)
        return {
            'name': _('Download File'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'portfolio.works.report.xlsx',
            'res_id': self.id,
            'target': 'new',
        }