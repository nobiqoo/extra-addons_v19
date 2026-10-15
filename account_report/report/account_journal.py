# -*- coding: utf-8 -*-

from odoo import _, models, fields

REPORT_TYPE = {
    'local': 'Local',
    'ifrs': 'NIIF'
}


class ReportJournal(models.AbstractModel):
    _name = 'report.account_report.account_journal'
    _description = 'Balance Report'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        format_border = workbook.add_format({'border': True})
        format_bold = workbook.add_format({'border': True, 'bold': True})
        format_old = workbook.add_format({'bold': True})
        format_color = workbook.add_format(
            {'border': True, 'bold': True, 'bg_color': '#ADD8E6'})
        format_num = workbook.add_format(
            {'border': True, 'num_format': '$#,##0.00'})
        format_number = workbook.add_format(
            {'border': True, 'bold': True, 'num_format': '$#,##0.00'})
        format_date = workbook.add_format({'num_format': 'dd-mm-yy'})
        format_right = workbook.add_format({'align': 'right'})

        worksheet = workbook.add_worksheet()

        now = fields.Datetime.context_timestamp(
            self,
            fields.Datetime.now()).strftime('%d-%m-%Y %H:%M:%S')
        date_process = fields.Datetime.context_timestamp(
            self,
            objs.date_process).strftime('%Y/%m/%d %H:%M:%S')

        # Info
        worksheet.write(0, 0, _('INFORME'), format_old)
        report_name = _('Libro Oficial Diario')
        worksheet.write(0, 1, report_name.upper())
        worksheet.write(1, 0, _('TIPO'), format_old)
        worksheet.write(1, 1, REPORT_TYPE.get(objs.report_type))
        worksheet.write(2, 0, _('COMPAÑÍA'), format_old)
        worksheet.write(2, 1, self.env.company.name)
        worksheet.write(3, 0, 'NIT', format_old)
        worksheet.write(3, 1, self.env.company.vat or '')
        worksheet.write(0, 3, _('FECHA PROCESO'), format_old)
        worksheet.write(0, 4, date_process, format_right)
        worksheet.write(1, 3, _('DESDE'), format_old)
        worksheet.write(1, 4, objs.date_from.strftime('%Y/%m/%d'), format_date)
        worksheet.write(2, 3, _('HASTA'), format_old)
        worksheet.write(2, 4, objs.date_to.strftime('%Y/%m/%d'), format_date)

        # Header
        report_header = objs.prepare_header()
        for i, title in enumerate(report_header):
            worksheet.write(5, i, str(title[1]).upper(), format_color)

        # Sheet
        report_data = data.get('report_data')

        cw = {}
        for i, value in enumerate(report_data):
            is_bold = value.get('bold')
            for j, header in enumerate(report_header):
                key = header[0]
                cw[str(j)] = cw.get(str(j), []) + [len(str(value[key]))]

                if key in ('debit', 'credit'):
                    format_key = is_bold and format_number or format_num
                    worksheet.write(i+6, j, value[key] or 0, format_key)
                else:
                    format_key = is_bold and format_bold or format_border
                    worksheet.write(i+6, j, value[key] or '', format_key)

        # Column
        for key in cw.keys():
            worksheet.set_column(
                int(key),
                int(key),
                max(x for x in cw[key]) + 4
            )

    def _get_report_values(self, docids, data=None):
        # get the report action back as we will need its data
        report = self.env['ir.actions.report']._get_report_from_name(
            'account_report.account_journal')
        # get the records selected for this rendering of the report
        obj = self.env[report.model].browse(docids)
        # return a custom rendering context

        return {
            "doc_ids": docids,
            "doc_model": "account.journal.wizard",
            "docs": self.env["account.journal.wizard"].browse(docids),
        }
