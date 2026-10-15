# -*- coding: utf-8 -*-


from odoo import fields, models, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import base64
import datetime
import xlsxwriter
from io import BytesIO
import io


class ReportInvoice(models.TransientModel):
    _name = "report.invoice"
    _description = 'Reporte de productos facturados'

    name = fields.Char(
        'Nombre', default='Informe de Facturados', readonly=True)
    date_from = fields.Datetime('Desde', required=True, default=(
        fields.Datetime.now() - relativedelta(month=1)))
    date_to = fields.Datetime('Hasta', required=True,
                              default=(fields.Datetime.now()))
    partner_ids = fields.Many2many('res.partner', string='Clientes')
    xls_file = fields.Binary(string="XLS file")
    xls_filename = fields.Char()

    def analysis(self):
        view_id = self.env['ir.ui.view'].search(
            [('name', '=', 'account.view_account_invoice_report_pivot')])
        dt_from = str(self.date_from)
        dt_to = str(self.date_to)
        domain = [('invoice_date', '>', dt_from),
                  ('invoice_date', '<=', dt_to)]
        return {
            'domain': domain,
            'name': 'Análisis de Facturados',
            'view_type': 'form',
            'view_mode': 'pivot',
            'view_id': view_id.id,
            'res_model': 'account.invoice.report',
            'type': 'ir.actions.act_window'
        }

    def _compute_excel(self):
        def _add_wh(fld, tbl):
            return " AND {} IN ({})".format(fld, ','.join(str(x.id) for x in tbl))

        # APLICAR FILTROS
        wh = ''
        if self.partner_ids:
            wh = _add_wh('so.partner_id', self.partner_ids)
        cr = self.env.cr
        dt_from = str(self.date_from)
        dt_to = str(self.date_to)
        cr.execute(f'''SELECT
                            so.date_order,
                            so.name,
                            am.name,
                            aa.name,
                            pt.default_code,
                            pt.name,
                            pc.name,
                            pb.name,
                            uu.name,
                            CASE
                            WHEN am.move_type = 'out_refund' THEN aml.quantity * (-1)
                            ELSE sol.product_uom_qty END,
                            CASE
                            WHEN am.move_type = 'out_refund' THEN aml.price_subtotal * (-1)
                            ELSE sol.price_subtotal END,
                            rp.vat,
                            rp.name,
                            rc2.name,
                            rc.name,
                            rp2.name,
                            cm.name

                        FROM sale_order_line sol
                            INNER JOIN sale_order so ON sol.order_id = so.id
                            INNER JOIN account_analytic_account aa ON so.analytic_account_id = aa.id
                            INNER JOIN product_product pp ON sol.product_id = pp.id
                            INNER JOIN product_template pt ON pt.id = pp.product_tmpl_id
                            INNER JOIN account_move_line aml ON so.id = aml.order_sale_id AND pp.id = aml.product_id
                            INNER JOIN account_move am ON aml.move_id = am.id
                            INNER JOIN product_category pc ON pt.categ_id = pc.id
                            INNER JOIN uom_uom uu ON pt.uom_id = uu.id
                            INNER JOIN res_partner rp ON so.partner_id = rp.id
                            INNER JOIN res_users ru ON so.user_id = ru.id
                            INNER JOIN res_partner rp2 ON ru.partner_id = rp2.id
                            INNER JOIN crm_team cm ON so.team_id = cm.id
                            LEFT JOIN product_brand pb ON pt.product_brand_id = pb.id
                            LEFT JOIN res_city rc ON so.city_id = rc.id
                            LEFT JOIN res_city rc2 ON rp.city_id = rc2.id

                        WHERE
                            pt.detailed_type = 'product' AND
                            sol.product_uom_qty = sol.qty_invoiced AND
                            so.state = 'done' AND
                            am.state = 'posted' AND
                            so.date_order BETWEEN   '{dt_from}' AND '{dt_to}' {wh}

                        GROUP BY
                        so.name,
                        am.name,
                        pc.name,
                        pt.default_code,
                        pt.name,
                        so.date_order,
                        aa.name,
                        pb.name,
                        uu.name,
                        sol.product_uom_qty,
                        aml.quantity,
                        sol.price_subtotal,
                        aml.price_subtotal,
                        rp.vat,
                        rp.name,
                        rc2.name,
                        rc.name,
                        rp2.name,
                        cm.name,
                        am.move_type
                      ''')
        result = cr.fetchall()
        return result

    def get_xlsx_report(self):
        result = self._compute_excel()
        output = io.BytesIO()
        titles = [
            'Fecha',
            'Orden de venta',
            '# Factura',
            'Cuenta',
            'Referencia Interna',
            'Producto',
            'Categoria',
            'Marca',
            'Unidad de medida',
            'Cantidad',
            'Valor',
            'Nit',
            'Cliente',
            'Ciudad Cliente',
            'Ciudad Factura',
            'Vendedor',
            'Equipo de ventas'
        ]
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet()

        # Formants
        titles_format = workbook.add_format()
        titles_format.set_align("center")
        titles_format.set_bold()
        worksheet.set_column("A:Q", 22)
        worksheet.set_row(0, 25)

        col_num = 0
        for title in titles:
            worksheet.write(0, col_num, title, titles_format)
            col_num += 1

        for index, data in enumerate(result):
            row = index + 1
            col_num = 0
            for d in data:
                if isinstance(d, datetime.date):
                    d = d.strftime("%Y-%m-%d")
                worksheet.write(row, col_num, d)
                col_num += 1

        workbook.close()
        xlsx_data = output.getvalue()

        self.xls_file = base64.encodebytes(xlsx_data)
        self.xls_filename = "report_invoice.xlsx"
