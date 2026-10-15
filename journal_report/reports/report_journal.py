# -- coding: utf-8 --

from odoo import fields, models

from dateutil.relativedelta import relativedelta
import base64
import datetime
import xlsxwriter
from io import BytesIO
import io


class ReportPurchase(models.TransientModel):
    _name = 'journal.audit.report'
    _description = 'Reporte de Auditoria de Diarios'

    name = fields.Char('Nombre', readonly=True, default='Reporte de Auditoría')
    journal_ids = fields.Many2many(
        'account.journal', string='Diario', copy=False)
    date_from = fields.Date('Desde', required=True, default=(
        fields.Date.today() - relativedelta(month=1)))
    date_to = fields.Date('Hasta', required=True,
                          default=(fields.Date.today()))

    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char()

    # noinspection PyMethodMayBeStatic

    def extended_compute_fields(self):
        """
        inherit on extended modules
        """
        add_fields_insert = add_fields_select = add_fields_from = ''
        return add_fields_insert, add_fields_select, add_fields_from

    def compute_report(self):
        def _add_where(table, fld, vl):
            return f" AND {table}.{fld} IN ({','.join(str(x.id) for x in vl)})"

        cr = self._cr
        wh = ''
        uid = self.env.user.id
        dt_now = fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dt_from = str(self.date_from)
        dt_to = str(self.date_to)
        if self.journal_ids:
            wh += _add_where('aml', 'journal_id', self.journal_ids)

        # add_fields_insert, add_fields_select, add_fields_from = self.extended_compute_fields()

        cr.execute(f'DELETE FROM audit_journal_line')

        qry = f'''
            INSERT INTO audit_journal_line (date, move_id, partner_vat, partner_id, account_id, name_aml, journal_id, debit, credit, state, create_date, write_date)
                SELECT
                    am.date,
                    am.create_date,
                    aml.move_id,
                    rp.vat,
                    aml.partner_id,
                    aml.account_id,
                    aml.name,
                    aml.journal_id,
                    COALESCE(SUM(aml.debit), 0.0),
                    COALESCE(SUM(aml.credit), 0.0),
                    am.state,
                        '{dt_now}',
                        '{dt_now}'


            FROM
                account_move_line aml
                LEFT JOIN account_move am ON aml.move_id = am.id
                LEFT JOIN account_journal aj ON am.journal_id = aj.id
                LEFT JOIN account_account aa ON aml.account_id = aa.id
                LEFT JOIN res_partner rp ON aml.partner_id = rp.id

            WHERE

                am.date BETWEEN   '{dt_from}' AND '{dt_to}'
                {wh}
            GROUP BY
            am.date,
            am.create_date,
            aml.move_id,
            aml.partner_id,
            aml.account_id,
            aml.name,
            aml.journal_id,
            rp.vat,
            am.state
            ORDER BY
            aml.move_id, am.date, aml.account_id
        '''
        cr.execute(qry)

    def _button_excel(self):
        def _add_where(table, fld, vl):
            return f" AND {table}.{fld} IN ({','.join(str(x.id) for x in vl)})"

        uid = self.env.user.id
        cr = self._cr
        wh = ''
        uid = self.env.user.id
        dt_now = fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dt_from = str(self.date_from)
        dt_to = str(self.date_to)
        if self.journal_ids:
            wh += _add_where('aml', 'journal_id', self.journal_ids)

        excel_qry = f'''
            SELECT
                am.date,
                am.create_date,
                am.name,
                rp.vat,
                rp.name,
                aa.code,
                aml.name,
                COALESCE(SUM(aml.debit), 0.0),
                COALESCE(SUM(aml.credit), 0.0),
                CASE
                    WHEN am.state = 'draft' THEN 'Borrador'
                    WHEN am.state = 'posted' THEN 'Publicado'
                    ELSE 'Cancelado'
                END

            FROM
                account_move_line aml
                LEFT JOIN account_move am ON aml.move_id = am.id
                LEFT JOIN account_journal aj ON aml.journal_id = aj.id
                LEFT JOIN account_account aa ON aml.account_id = aa.id
                LEFT JOIN res_partner rp ON aml.partner_id = rp.id

            WHERE

                am.date BETWEEN   '{dt_from}' AND '{dt_to}'
                {wh}
            GROUP BY
            am.date,
            am.create_date,
            am.name,
            rp.name,
            rp.vat,
            aa.code,
            aml.name,
            am.state
            ORDER BY
            am.name, am.date, aa.code
        '''
        cr.execute(excel_qry)
        result = cr.fetchall()

        return result

    def get_xlsx_report(self):
        result = self._button_excel()
        output = io.BytesIO()
        titles = ['FECHA',
                  'FECHA DE ACTUALIZACIÓN',
                  'ASIENTO',
                  'NIT',
                  'ASOCIADO',
                  'CUENTA',
                  'ETIQUETA',
                  'DEBITO',
                  'CREDITO',
                  'ESTADO'
                  ]

        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet()

        # Formants
        titles_format = workbook.add_format()
        titles_format.set_align("center")
        titles_format.set_bold()
        worksheet.set_column("A:G", 22)
        worksheet.set_row(0, 25)
        money_format = workbook.add_format({'num_format': '$#,##0.00'})

        col_num = 0
        for title in titles:
            worksheet.write(0, col_num, title, titles_format)
            col_num += 1

        for index, data in enumerate(result):
            row = index + 1
            col_num = 0
            for i, d in enumerate(data):
                if i in [6, 7]:
                    worksheet.write(row, col_num, d, money_format)
                else:
                    worksheet.write(row, col_num, d)
                if isinstance(d, datetime.date):
                    d = d.strftime("%Y-%m-%d")
                    worksheet.write(row, col_num, d)
                col_num += 1

        workbook.close()
        xlsx_data = output.getvalue()

        self.xls_file = base64.encodebytes(xlsx_data)
        self.xls_filename = "audit_journal.xlsx"

    def button_bi(self):
        self.compute_report()
        view_id = self.env['ir.ui.view'].search(
            [('name', '=', 'purchase_reports.report_purchase_line_pivot')])
        dt_from = str(self.date_from)
        dt_to = str(self.date_to)
        domain = [('date', '>', dt_from), ('date', '<=', dt_to)]
        return {
            'domain': domain,
            'name': 'Análisis de Diarios',
            'view_type': 'form',
            'view_mode': 'pivot',
            'view_id': view_id.id,
            'res_model': 'audit.journal.line',
            'type': 'ir.actions.act_window'
        }


class ReportPurchaseLine(models.Model):
    _name = 'audit.journal.line'
    _description = 'Lineas del reporte de Auditoria'

    partner_id = fields.Many2one(
        'res.partner', 'Asociado', copy=False, readonly=True)
    partner_vat = fields.Char('NIT', copy=False, readonly=True, index=True)
    date = fields.Date(readonly=True, string="Fecha", copy=False, index=True)
    create_date = fields.Date(readonly=True, string="Fecha de Actualizacion", copy=False, index=True)
    move_id = fields.Many2one(
        'account.move', string="Asiento", copy=False, readonly=True)
    journal_id = fields.Many2one(
        'account.journal', 'Diario', copy=False, readonly=True)
    account_id = fields.Many2one(
        'account.account', 'Cuenta', copy=False, readonly=True)
    name_aml = fields.Char('Etiqueta', copy=False, readonly=True)
    debit = fields.Float('Debito', copy=False, readonly=True)
    credit = fields.Float('Cradito', copy=False, readonly=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Publicado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', readonly=True)
