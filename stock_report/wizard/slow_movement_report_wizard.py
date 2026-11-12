import base64
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from odoo import fields, models


class SlowMovementReportWizard(models.TransientModel):
    _name = 'slow.movement.report.wizard'
    _description = 'Wizard Reporte Lento Movimiento'

    file_data = fields.Binary(string='Archivo', readonly=True)
    file_name = fields.Char(string='Nombre archivo', readonly=True)

    def action_generate_excel(self):
        self.ensure_one()

        self.env.cr.execute(self._get_report_query(), self._get_report_query_params())
        rows = self.env.cr.dictfetchall()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Lento Movimiento')
        formats = self._get_workbook_formats(workbook)

        headers = self._get_report_headers()
        last_column = xl_col_to_name(len(headers) - 1)
        sheet.merge_range('A1:%s1' % last_column, 'Reporte de Lento Movimiento', formats['title'])

        for col, header in enumerate(headers):
            sheet.write(1, col, header, formats['header'])

        row_num = 2
        for row in rows:
            self._write_report_row(sheet, row_num, row, formats)
            row_num += 1

        self._set_column_widths(sheet)

        workbook.close()
        output.seek(0)

        file_name = 'reporte_lento_movimiento_%s.xlsx' % datetime.now(ZoneInfo('America/Bogota')).strftime('%Y%m%d_%H%M%S')

        self.write({
            'file_data': base64.b64encode(output.read()),
            'file_name': file_name,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=slow.movement.report.wizard&id=%s&field=file_data&filename_field=file_name&download=true' % self.id,
            'target': 'self',
        }

    def _get_report_query_params(self):
        return {
            'report_date': datetime.now(ZoneInfo('America/Bogota')).date(),
            'company_ids': tuple(self.env.companies.ids),
        }

    def _get_report_query(self):
        return """
            WITH productos AS (
                SELECT
                    pp.id AS product_id,
                    pp.default_code,
                    pt.name AS product_name,
                    pp.standard_price
                FROM product_product pp
                JOIN product_template pt
                    ON pt.id = pp.product_tmpl_id
                WHERE pt.type IN ('product', 'consu')
            ),

            quants AS (
                SELECT
                    sq.product_id,
                    wh.id AS warehouse_id,
                    sq.location_id,
                    sq.company_id,
                    loc.complete_name AS ubicacion,
                    COALESCE(wh.name, 'Sin almacén') AS almacen,
                    SUM(sq.quantity - COALESCE(sq.reserved_quantity, 0)) AS existencia_mano
                FROM stock_quant sq
                JOIN stock_location loc
                    ON loc.id = sq.location_id
                    AND loc.usage = 'internal'

                JOIN stock_warehouse wh
                    ON loc.parent_path LIKE CONCAT('%%/', wh.view_location_id::text, '/%%')
                    AND wh.company_id = sq.company_id

                JOIN productos p
                    ON p.product_id = sq.product_id

                WHERE sq.company_id IN %(company_ids)s
                    AND EXISTS (
                        SELECT 1
                        FROM stock_location root
                        WHERE root.usage IN ('internal', 'view')
                            AND (
                                root.id = wh.lot_stock_id
                                OR LOWER(TRIM(root.name)) IN ('taller', 'existencias')
                            )
                            AND root.parent_path LIKE CONCAT('%%/', wh.view_location_id::text, '/%%')
                            AND loc.parent_path LIKE CONCAT(root.parent_path, '%%')
                    )

                GROUP BY
                    sq.product_id,
                    sq.location_id,
                    sq.company_id,
                    loc.complete_name,
                    wh.id,
                    wh.name

                HAVING SUM(sq.quantity - COALESCE(sq.reserved_quantity, 0)) > 0
            ),

            movimientos AS (
                SELECT
                    q.product_id,
                    q.location_id,
                    q.company_id,
                    MAX(sm.date) FILTER (
                        WHERE sml.location_dest_id = q.location_id
                        AND sml.location_id != q.location_id
                    ) AS fecha_ingreso,
                    MAX(sm.date) FILTER (
                        WHERE sml.location_id = q.location_id
                        AND sml.location_dest_id != q.location_id
                    ) AS fecha_ultima_salida,
                    MAX(sm.date) AS ultimo_movimiento_sistema,
                    (ARRAY_AGG(
                        CASE
                            WHEN sml.location_id = sml.location_dest_id THEN 'Interno'
                            WHEN sml.location_id = q.location_id THEN 'Salida'
                            ELSE 'Entrada'
                        END ORDER BY sm.date DESC, sm.id DESC, sml.id DESC
                    ))[1] AS tipo_movimiento
                FROM quants q
                JOIN stock_move_line sml ON sml.product_id = q.product_id
                    AND (sml.location_id = q.location_id
                         OR sml.location_dest_id = q.location_id)
                JOIN stock_move sm ON sm.id = sml.move_id
                    AND sm.company_id = q.company_id
                WHERE sm.state = 'done' AND sml.quantity > 0
                GROUP BY q.product_id, q.location_id, q.company_id
            )
            {extra_ctes}

            SELECT
                q.almacen,
                q.ubicacion,
                p.default_code AS referencia,
                COALESCE(p.product_name->>'es_CO', p.product_name->>'en_US') AS descripcion,
                q.existencia_mano,

                COALESCE((p.standard_price->>q.company_id::text)::numeric, 0) AS costo_unitario,

                q.existencia_mano * COALESCE((p.standard_price->>q.company_id::text)::numeric, 0) AS total,

                m.fecha_ingreso AT TIME ZONE 'UTC' AT TIME ZONE 'America/Bogota' AS fecha_ingreso,
                m.tipo_movimiento,

                m.fecha_ultima_salida AT TIME ZONE 'UTC' AT TIME ZONE 'America/Bogota'
                    AS fecha_ultima_salida,
                m.ultimo_movimiento_sistema AT TIME ZONE 'UTC' AT TIME ZONE 'America/Bogota'
                    AS ultimo_movimiento_sistema,
                %(report_date)s::date - (
                    m.ultimo_movimiento_sistema AT TIME ZONE 'UTC' AT TIME ZONE 'America/Bogota'
                )::date AS dias_desde_ultimo_movimiento
                {extra_columns}

            FROM productos p

            JOIN quants q
                ON q.product_id = p.product_id

            LEFT JOIN movimientos m
                ON m.product_id = p.product_id
                AND m.location_id = q.location_id
                AND m.company_id = q.company_id
            {extra_joins}

            ORDER BY dias_desde_ultimo_movimiento DESC NULLS LAST
        """.format(
            extra_ctes=self._get_extra_query_ctes(),
            extra_columns=self._get_extra_query_columns(),
            extra_joins=self._get_extra_query_joins(),
        )

    def _get_extra_query_ctes(self):
        return ''

    def _get_extra_query_columns(self):
        return ''

    def _get_extra_query_joins(self):
        return ''

    def _get_workbook_formats(self, workbook):
        return {
            'title': workbook.add_format({
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'font_size': 14,
                'border': 1,
            }),
            'header': workbook.add_format({
                'bold': True,
                'bg_color': '#D9EAF7',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True,
            }),
            'text': workbook.add_format({'border': 1}),
            'number': workbook.add_format({'border': 1, 'num_format': '#,##0.00'}),
            'integer': workbook.add_format({'border': 1, 'num_format': '0'}),
            'date': workbook.add_format({'border': 1, 'num_format': 'dd-mm-yyyy hh:mm:ss'}),
            'date_only': workbook.add_format({'border': 1, 'num_format': 'dd-mm-yyyy'}),
        }

    def _get_report_headers(self):
        return [
            'Almacén',
            'Ubicación',
            'Referencia',
            'Descripción',
            'Disponible para consumo',
            'Costo unitario',
            'Total',
            'Fecha último ingreso',
            'Fecha de la última salida',
            'Último movimiento Sistema',
            'Días desde último movimiento',
            'Tipo de último movimiento',
        ] + self._get_extra_report_headers()

    def _get_extra_report_headers(self):
        return []

    def _write_report_row(self, sheet, row_num, row, formats):
        for column, key in enumerate(('almacen', 'ubicacion', 'referencia', 'descripcion')):
            sheet.write(row_num, column, row.get(key) or '', formats['text'])
        for column, key in enumerate(('existencia_mano', 'costo_unitario', 'total'), start=4):
            sheet.write_number(row_num, column, float(row.get(key) or 0), formats['number'])
        for column, key in enumerate(
            ('fecha_ingreso', 'fecha_ultima_salida', 'ultimo_movimiento_sistema'), start=7,
        ):
            self._write_datetime(sheet, row_num, column, row.get(key), formats['date'], formats['text'])
        days = row.get('dias_desde_ultimo_movimiento')
        if days is None:
            sheet.write(row_num, 10, '', formats['text'])
        else:
            sheet.write_number(row_num, 10, int(days), formats['integer'])
        sheet.write(row_num, 11, row.get('tipo_movimiento') or '', formats['text'])
        self._write_extra_report_columns(sheet, row_num, 12, row, formats)

    def _write_extra_report_columns(self, sheet, row_num, start_col, row, formats):
        return

    def _write_datetime(self, sheet, row_num, col_num, value, date_format, empty_format):
        if not value:
            sheet.write(row_num, col_num, '', empty_format)
            return
        if isinstance(value, str):
            value = fields.Datetime.from_string(value)
        sheet.write_datetime(row_num, col_num, value, date_format)

    def _write_date(self, sheet, row_num, col_num, value, date_format, empty_format):
        if not value:
            sheet.write(row_num, col_num, '', empty_format)
            return
        if isinstance(value, str):
            value = fields.Date.from_string(value)
        sheet.write_datetime(row_num, col_num, datetime.combine(value, datetime.min.time()), date_format)

    def _set_column_widths(self, sheet):
        sheet.set_column('A:A', 20)
        sheet.set_column('B:B', 30)
        sheet.set_column('C:C', 18)
        sheet.set_column('D:D', 40)
        sheet.set_column('E:G', 18)
        sheet.set_column('H:J', 22)
        sheet.set_column('K:L', 24)
        self._set_extra_column_widths(sheet)

    def _set_extra_column_widths(self, sheet):
        return
