# -*- coding: utf-8 -*-

from odoo import models
from pytz import timezone

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
        worksheet = workbook.add_worksheet('Valuation')
        fbold = workbook.add_format({'bold': True})
        fdate = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
        ffloat = workbook.add_format({'num_format': '#,##0.00'})
        fcurrency = workbook.add_format({'num_format': '$#,##0.00'})
        # Header
        for c, header in enumerate(headers):
            worksheet.write(0, c, header, fbold)
        # Sheet
        blayers, layers = objs.ation_data()

        seq = 1
        alayers = []
        for l in blayers:
            l.update(seq=seq)
            alayers.append(l)
            seq += 1
        for l in layers:
            l.update(seq=seq)
            alayers.append(l)
            seq += 1

        for r, layer in enumerate(layers):
            Move = self.env['stock.move']
            move = Move.browse(layer.get('id'))

            date = layer.get('date')
            # date_utc = UTC.localize(date)
            user_tz = timezone(self.env.user.tz or 'UTC')
            date = date.astimezone(user_tz)
            date = date.replace(tzinfo=None)
            description = layer.get('value_justification') or ''
            reference = move and move.reference or ''
            origin = move and move.origin or ''
            partner = move.partner_id.display_name if move and move.partner_id else ''
            product = layer.get('product_id')[1]
            category = self.env['product.product'].browse(layer.get('product_id')[0]).categ_id.name
            location = move and self.env._(move.location_id.complete_name) or ''
            location_dest = move and self.env._(
                move.location_dest_id.complete_name) or ''
            quantity = layer.get('quantity')
            uom = self.env._(layer.get('product_uom')[1])
            value = layer.get('value')
            unit = value / quantity if quantity else 0.0

            flayers = [l for l in alayers if l.get('product_id')[0] == layer.get(
                'product_id')[0] and l.get('seq') < layer.get('seq')]
            quanity_former = flayers and sum(
                [l.get('quantity') for l in flayers]) or 0.00
            value_former = flayers and sum(
                [l.get('value') for l in flayers]) or 0.00
            cost_former = value_former / (quanity_former or 1)

            quantity_final = quanity_former + quantity
            # cost = ((quanity_former * cost_former) + (quantity * unit_cost)) / quantity_final
            cost = (value_former + value) / (quantity_final or 1)

            flayers = [l for l in alayers if l.get('product_id')[0] == layer.get(
                'product_id')[0] and l.get('seq') < layer.get('seq')]
            quanity_former = flayers and sum(
                [l.get('quantity') for l in flayers]) or 0.00
            value_former = flayers and sum(
                [l.get('value') for l in flayers]) or 0.00
            cost_former = value_former / (quanity_former or 1)

            quantity_final = quanity_former + quantity
            # cost = ((quanity_former * cost_former) + (quantity * unit_cost)) / quantity_final
            cost = (value_former + value) / (quantity_final or 1)

            worksheet.write(r+1, 0, date, fdate)
            worksheet.write(r+1, 1, description)
            worksheet.write(r+1, 2, reference)
            worksheet.write(r+1, 3, origin)
            worksheet.write(r+1, 4, partner)
            worksheet.write(r+1, 5, category)
            worksheet.write(r+1, 6, product)
            worksheet.write(r+1, 7, location)
            worksheet.write(r+1, 8, location_dest)
            worksheet.write(r+1, 9, quanity_former, ffloat)
            worksheet.write(r+1, 10, quantity, ffloat)
            worksheet.write(r+1, 11, quantity_final, ffloat)
            worksheet.write(r+1, 12, uom)
            worksheet.write(r+1, 13, unit, fcurrency)
            worksheet.write(r+1, 14, value, fcurrency)
            worksheet.write(r+1, 15, cost_former, fcurrency)
            worksheet.write(r+1, 16, cost, fcurrency)
