# -*- coding: utf-8 -*-
import logging
from odoo import models
from pytz import timezone

_logger = logging.getLogger(__name__)

headers = [
    'Fecha',
    'Descripción',
    'Referencia',
    'Origen',
    'Tercero',
    'Categoria',
    'Producto',
    'De',
    'A',
    'C. anterior',
    'Cantidad',
    'C. final',
    'UdM',
    'Costo unitario',
    'Valor',
    'Costo anterior',
    'Costo promedio',
]


class ReportStockValuation(models.AbstractModel):
    _name = 'report.stock_report.report_stock_valuation'
    _description = 'Report Stock Valuation'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, objs):
        # Habilitar constant_memory para evitar cargar todo en RAM
        # Sin esto, xlsxwriter acumula TODAS las celdas en memoria
        workbook.constant_memory = True
        # Excel no soporta timezones - xlsxwriter los remueve automáticamente
        workbook.remove_timezone = True
        
        worksheet = workbook.add_worksheet('Valuation')
        fbold = workbook.add_format({'bold': True})
        fdate = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        ffloat = workbook.add_format({'num_format': '#,##0.00'})
        fcurrency = workbook.add_format({'num_format': '$#,##0.00'})
        
        # Header
        for c, header in enumerate(headers):
            worksheet.write(0, c, header, fbold)
        
        user_tz = timezone(self.env.user.tz or 'UTC')
        
        # Sheet
        product_cumulative, layers = objs.action_data()
        product_cumulative = product_cumulative or {}
        
        row = 1
        row_batch = 0  # contador para logging de progreso
        _logger.warning('generating valuation report INIT - constant_memory=True')
        
        for layer in layers:
            product = layer.get('product_id')
            quantity = layer.get('quantity') or 0.00
            value = layer.get('value') or 0.00

            if product not in product_cumulative:
                product_cumulative[product] = {
                    'quantity': 0.00,
                    'value': 0.00,
                }

            quantity_former = product_cumulative[product]['quantity']
            value_former = product_cumulative[product]['value']
            quantity_final = quantity_former + quantity
            cost_former = value_former / (quantity_former or 1)
            cost = (value_former + value) / (quantity_final or 1)

            date = layer.get('create_date')
            if date:
                # UTC → zona horaria local del usuario
                date = date.astimezone(user_tz)
            else:
                date = None
            description = layer.get('description')
            product_name = layer.get('product_name', '-') or ''
            product_code = layer.get('product_code', '-') or ''
            reference = layer.get('sm_reference', '') or ''
            origin = layer.get('sm_origin', '') or ''
            partner = layer.get('rp_name', '') or ''
            category = layer.get('pc_name', '') or ''
            location = layer.get('loc_name', '') or ''
            location_dest = layer.get('loc_dest_name', '') or ''
            uom = layer.get('uom_name', '') or ''
            unit = layer.get('unit_cost')

            worksheet.write(row, 0, date, fdate)
            worksheet.write(row, 1, description)
            worksheet.write(row, 2, reference)
            worksheet.write(row, 3, origin)
            worksheet.write(row, 4, partner)
            worksheet.write(row, 5, category)
            worksheet.write(row, 6, f"[{product_code}] {product_name}")
            worksheet.write(row, 7, location)
            worksheet.write(row, 8, location_dest)
            worksheet.write(row, 9, quantity_former, ffloat)
            worksheet.write(row, 10, quantity, ffloat)
            worksheet.write(row, 11, quantity_final, ffloat)
            worksheet.write(row, 12, uom)
            worksheet.write(row, 13, unit, fcurrency)
            worksheet.write(row, 14, value, fcurrency)
            worksheet.write(row, 15, cost_former, fcurrency)
            worksheet.write(row, 16, cost, fcurrency)
            row += 1
            row_batch += 1
            
            if row_batch % 10000 == 0:
                _logger.warning(f'valuation report progress: {row_batch} rows written')

            product_cumulative[product]['quantity'] += quantity
            product_cumulative[product]['value'] += value
        
        _logger.warning(f'valuation report generated successfully with {row - 1} lines')
