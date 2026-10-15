from odoo import models, fields, _
import base64
import io
import xlsxwriter
from datetime import date
from odoo.exceptions import ValidationError

class ReportAssetWizard(models.TransientModel):
    _name = 'report.asset.wizard'
    _description = 'Wizard to generate report assets'

    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')

    def _get_domain(self):
        domain = [('state', 'not in', ['draft', 'model', 'cancelled'])]
        if self.date_from and self.date_to and (self.date_from > self.date_to):
            raise ValidationError(_('The end date cannot be less than the initial date.'))
        if self.date_from:
            domain.append(('acquisition_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('acquisition_date', '<=', self.date_to))
        return domain

    def _get_assets(self):
        domain = self._get_domain()
        return self.env['account.asset'].search(domain)

    def action_generate_excel(self):
        assets = self._get_assets()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })

        worksheet = workbook.add_worksheet('Activos Fijos')

        # Estilos básicos
        header_format = workbook.add_format({'font_name': 'Arial', 'font_size': 9, 'bg_color': '#0B1B2B', 'font_color': 'white', 'align': 'center'})
        bold = workbook.add_format({'bold': True, 'border': 1, 'align': 'center'})
        normal = workbook.add_format({'border': 1})
        normal_center = workbook.add_format({'border': 1, 'align': 'center'})
        currency_format = workbook.add_format({
            'num_format': '$#,##0.00', 
            'border': 1
        })
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'border': 1
        })

        last_year = str(date.today().year-1)
        current_year = str(date.today().year)
        cut_last_year = current_year[2:]

        headers = [
            'Número Activo', 'Proveedor', 'Factura', 'Descripción',
            'Categoría', 'Mes compra', 'Año compra', 'Fecha compra', 
            'Fecha Alta', 'Costo', 'Valor Rescate',
            'Vida útil', 'Depreciación acumulada año {year}'.format(year=last_year), 'Valor en libros {year}'.format(year=last_year),
            'Compras', 'Jan-{year}'.format(year=cut_last_year), 'Feb-{year}'.format(year=cut_last_year), 'Mar-{year}'.format(year=cut_last_year),
            'Apr-{year}'.format(year=cut_last_year), 'May-{year}'.format(year=cut_last_year), 'Jun-{year}'.format(year=cut_last_year),
            'Jul-{year}'.format(year=cut_last_year), 'Aug-{year}'.format(year=cut_last_year), 'Sep-{year}'.format(year=cut_last_year),
            'Oct-{year}'.format(year=cut_last_year), 'Nov-{year}'.format(year=cut_last_year), 'Dec-{year}'.format(year=cut_last_year),
            'Depr {year}'.format(year=current_year), 'Bajas y/o salidas', 'Fecha Baja', 'Saldo {year}'.format(year=current_year),
        ]

        row = 0
        for col_num, header in enumerate(headers):
            worksheet.write(row, col_num, header, header_format)

        for asset in assets:
            row+=1
            worksheet.write(row, 0, asset.active_number or '', normal)
            worksheet.write(row, 1, asset.provider_id.name or '', normal)
            worksheet.write(row, 2, asset._get_name_invoices(), normal)
            worksheet.write(row, 3, asset.description or '', normal)
            worksheet.write(row, 4, asset.model_id.name or '', normal)
            worksheet.write(row, 5, asset._get_month_purchase(), normal)
            worksheet.write(row, 6, asset._get_year_purchase(), normal)
            worksheet.write(row, 7, asset.acquisition_date, date_format)
            worksheet.write(row, 8, asset.prorata_date, date_format)
            worksheet.write(row, 9, asset.original_value, currency_format)
            worksheet.write(row, 10, asset.salvage_value, currency_format)
            worksheet.write(row, 11, asset.method_number, normal_center)
            worksheet.write(row, 12, asset.get_depretiation_last_year(), currency_format)
            worksheet.write(row, 13, asset.get_depretiation_last_year(), currency_format)
            worksheet.write(row, 14, '', normal)
            worksheet.write(row, 15, asset.get_depretiation_in_month(1), currency_format)
            worksheet.write(row, 16, asset.get_depretiation_in_month(2), currency_format)
            worksheet.write(row, 17, asset.get_depretiation_in_month(3), currency_format)
            worksheet.write(row, 18, asset.get_depretiation_in_month(4), currency_format)
            worksheet.write(row, 19, asset.get_depretiation_in_month(5), currency_format)
            worksheet.write(row, 20, asset.get_depretiation_in_month(6), currency_format)
            worksheet.write(row, 21, asset.get_depretiation_in_month(7), currency_format)
            worksheet.write(row, 22, asset.get_depretiation_in_month(8), currency_format)
            worksheet.write(row, 23, asset.get_depretiation_in_month(9), currency_format)
            worksheet.write(row, 24, asset.get_depretiation_in_month(10), currency_format)
            worksheet.write(row, 25, asset.get_depretiation_in_month(11), currency_format)
            worksheet.write(row, 26, asset.get_depretiation_in_month(12), currency_format)
            worksheet.write(row, 27, asset.get_depretiation_current_year(), currency_format)
            worksheet.write(row, 28, '', normal)
            worksheet.write(row, 29, asset.discharge_date or '', date_format)
            worksheet.write(row, 30, asset.get_depretiation_residual(), currency_format)

        worksheet.set_column(0, len(headers) - 1, 20)

        workbook.close()

        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': 'Reporte_Activos_Fijos.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'report.asset.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            "type": "ir.actions.act_url",
            "url": '/web/content/%s?download=true' % attachment.id,
            "target": "self",
        }
