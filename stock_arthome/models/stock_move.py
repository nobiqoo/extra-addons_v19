# -*- coding: utf-8 -*-

import base64
import csv
import os
import re
import unicodedata

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import formatLang

LOT_IMPORT_FILE_EXTENSIONS = ('.xlsx', '.xls', '.csv', '.ods')
LOT_IMPORT_HEADER_KEYWORDS = ('lot', 'serie', 'serial')
LOT_IMPORT_NUMBER_REGEX = re.compile(r'^[+-]?(\d+([.,]\d+)*([.,]\d*)?|[.,]\d+)$')


def _normalize_text(value):
    value = unicodedata.normalize('NFD', str(value or ''))
    return value.encode('ascii', 'ignore').decode('ascii').lower().strip()


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _get_new_picking_values(self):
        vals = super()._get_new_picking_values()
        comment = self.sale_line_id.order_id[:1].delivery_comment
        if not comment and vals.get('pos_order_id'):
            comment = self.env['pos.order'].browse(vals['pos_order_id']).general_customer_note
        if comment:
            vals['delivery_comment'] = comment
        return vals

    @api.model
    def action_import_lot_line_vals_arthome(self, context_data, params, apply=False):
        """Valida la importación de lotes y devuelve las líneas válidas y las filas rechazadas."""
        if not context_data.get('default_product_id'):
            raise UserError(_("No product found to import Serials/Lots for."))
        default_vals = {
            key.removeprefix('default_'): value
            for key, value in context_data.items() if key.startswith('default_')
        }
        product = self.env['product.product'].browse(default_vals['product_id'])
        tracking = default_vals.get('tracking') or product.tracking
        line_uom = self.env['uom.uom'].browse(default_vals.get('uom_id') or product.uom_id.id)
        move_uom = self.env['uom.uom'].browse(params.get('move_uom_id') or line_uom.id)

        rows = self._read_lot_import_rows_arthome(params)
        valid_rows, errors = self._parse_lot_import_rows_arthome(rows, tracking, line_uom)
        valid_rows = self._validate_lot_import_rows_arthome(
            valid_rows, errors, default_vals, params, line_uom, move_uom)

        lines = self._prepare_lot_import_line_vals_arthome(
            valid_rows, default_vals, context_data, product, line_uom, apply=apply)
        errors.sort(key=lambda error: error['row'])
        warnings = [
            {'row': row['row'], 'lot_name': row['lot_name'], 'quantity': row['quantity_text'], 'reason': row['warning']}
            for row in valid_rows if row.get('warning')
        ]
        return {
            'lines': lines,
            'errors': errors,
            'warnings': warnings,
            'valid_count': len(valid_rows),
            'error_count': len(errors),
            'warning_count': len(warnings),
            'total_qty': sum(row['quantity'] for row in valid_rows),
            'uom_name': line_uom.display_name,
        }

    @api.model
    def _read_lot_import_rows_arthome(self, params):
        if params.get('file_content'):
            return self._read_lot_import_file_arthome(params['file_content'], params.get('file_name') or '')
        rows = []
        for row_number, line in enumerate((params.get('lot_text') or '').split('\n'), start=1):
            cells = line.replace('\r', '').replace(';', '\t').split('\t')
            if any(cell.strip() for cell in cells):
                rows.append((row_number, cells))
        return rows

    @api.model
    def _read_lot_import_file_arthome(self, file_content, file_name):
        extension = os.path.splitext(file_name.lower())[1]
        if extension not in LOT_IMPORT_FILE_EXTENSIONS:
            raise UserError(_("Unsupported file format. Please use one of: %s.", ', '.join(LOT_IMPORT_FILE_EXTENSIONS)))
        file_bytes = base64.b64decode(file_content)
        options = {'quoting': '"'}
        if extension == '.csv':
            options['separator'] = self._guess_lot_import_csv_separator_arthome(file_bytes)
        importer = self.env['base_import.import'].new({
            'res_model': self._name,
            'file': file_bytes,
            'file_name': file_name,
        })
        try:
            __, file_rows = importer._read_file(options)
        except UserError:
            raise
        except Exception as error:  # noqa: BLE001
            raise UserError(_("The file could not be read: %s", error)) from error
        # El lector de base_import ya descarta las filas vacías.
        return [(row_number, [str(cell) for cell in row]) for row_number, row in enumerate(file_rows, start=1)]

    @api.model
    def _guess_lot_import_csv_separator_arthome(self, file_bytes):
        try:
            text = file_bytes.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = file_bytes.decode('latin-1')
        sample = next((line for line in text.splitlines() if line.strip()), '')
        for separator in (';', '\t', ','):
            if separator in sample:
                return separator
        try:
            return csv.Sniffer().sniff(sample).delimiter
        except csv.Error:
            return ';'

    @api.model
    def _parse_lot_import_quantity_arthome(self, value):
        value = (value or '').replace('\xa0', '').replace(' ', '')
        if not LOT_IMPORT_NUMBER_REGEX.match(value):
            return None
        dots, commas = value.count('.'), value.count(',')
        if dots and commas:
            decimal_sep = ',' if value.rfind(',') > value.rfind('.') else '.'
            thousand_sep = '.' if decimal_sep == ',' else ','
            if value.count(decimal_sep) > 1:
                return None
            value = value.replace(thousand_sep, '').replace(decimal_sep, '.')
        elif commas:
            value = value.replace(',', '.') if commas == 1 else value.replace(',', '')
        elif dots > 1:
            value = value.replace('.', '')
        try:
            return float(value)
        except ValueError:
            return None

    @api.model
    def _is_lot_import_header_arthome(self, cells):
        first = _normalize_text(cells[0])
        second = cells[1].strip() if len(cells) > 1 else ''
        return (
            any(keyword in first for keyword in LOT_IMPORT_HEADER_KEYWORDS)
            and self._parse_lot_import_quantity_arthome(second) is None
        )

    @api.model
    def _parse_lot_import_rows_arthome(self, rows, tracking, line_uom):
        valid_rows, errors = [], []

        def add_error(row_number, lot_name, quantity_text, reason):
            errors.append({'row': row_number, 'lot_name': lot_name, 'quantity': quantity_text, 'reason': reason})

        for index, (row_number, cells) in enumerate(rows):
            if index == 0 and self._is_lot_import_header_arthome(cells):
                continue
            lot_name = cells[0].strip()
            quantity_text = cells[1].strip() if len(cells) > 1 else ''
            if not lot_name:
                add_error(row_number, lot_name, quantity_text, _("Missing lot/serial number."))
                continue
            if not quantity_text:
                if tracking == 'serial':
                    quantity_text = '1'
                else:
                    add_error(row_number, lot_name, quantity_text, _("Missing quantity."))
                    continue
            quantity = self._parse_lot_import_quantity_arthome(quantity_text)
            if quantity is None:
                add_error(row_number, lot_name, quantity_text, _("The quantity is not a valid number."))
                continue
            if line_uom.compare(quantity, 0) <= 0:
                add_error(row_number, lot_name, quantity_text, _("The quantity must be greater than zero."))
                continue
            if abs(line_uom.round(quantity) - quantity) > 1e-9:
                add_error(row_number, lot_name, quantity_text, _(
                    "The quantity has more decimals than the unit of measure allows (%(rounding)s).",
                    rounding=formatLang(self.env, line_uom.rounding, dp='Product Unit')))
                continue
            if tracking == 'serial' and line_uom.compare(quantity, 1) != 0:
                add_error(row_number, lot_name, quantity_text, _("The quantity of a serial number must be 1."))
                continue
            valid_rows.append({
                'row': row_number,
                'lot_name': lot_name,
                'quantity': quantity,
                'quantity_text': quantity_text,
                'comment': cells[2].strip() if len(cells) > 2 else '',
                'dim': cells[3].strip() if len(cells) > 3 else '',
            })
        return valid_rows, errors

    @api.model
    def _validate_lot_import_rows_arthome(self, valid_rows, errors, default_vals, params, line_uom, move_uom):
        def reject(row, reason):
            errors.append({'row': row['row'], 'lot_name': row['lot_name'], 'quantity': row['quantity_text'], 'reason': reason})

        keep_lines = params.get('keep_lines')
        current_lines = (params.get('current_lines') or []) if keep_lines else []
        current_names = {line['lot_name'] for line in current_lines if line.get('lot_name')}

        company_id = default_vals.get('company_id') or self.env.company.id
        existing_names = set(self.env['stock.lot'].search([
            ('product_id', '=', default_vals['product_id']),
            '|', ('company_id', '=', company_id), ('company_id', '=', False),
            ('name', 'in', [row['lot_name'] for row in valid_rows]),
        ]).mapped('name'))

        seen_names = set()
        unique_rows = []
        for row in valid_rows:
            if row['lot_name'] in seen_names:
                reject(row, _("Duplicated lot/serial number in the imported data."))
            elif row['lot_name'] in current_names:
                reject(row, _("The lot/serial number is already in the current lines."))
            elif row['lot_name'] in existing_names:
                reject(row, _("The lot/serial number already exists for this product."))
            else:
                unique_rows.append(row)
            seen_names.add(row['lot_name'])

        demand = params.get('demand') or 0.0
        if move_uom.compare(demand, 0) <= 0:
            return unique_rows
        uoms = self.env['uom.uom'].browse({line['product_uom_id'] for line in current_lines if line.get('product_uom_id')})
        uom_by_id = {uom.id: uom for uom in uoms}
        running_qty = sum(
            uom_by_id[line['product_uom_id']]._compute_quantity(line.get('quantity') or 0.0, move_uom, round=False)
            if line.get('product_uom_id') in uom_by_id else line.get('quantity') or 0.0
            for line in current_lines
        )
        # Como en Odoo base, se puede registrar mas que la demanda: la fila se acepta con un aviso.
        for row in unique_rows:
            qty = line_uom._compute_quantity(row['quantity'], move_uom, round=False)
            running_qty += qty
            if move_uom.compare(running_qty, demand) > 0:
                row['warning'] = self._get_lot_import_excess_warning_arthome(
                    min(qty, running_qty - demand), demand, move_uom)
        accepted_rows = unique_rows
        return accepted_rows

    @api.model
    def _get_lot_import_excess_warning_arthome(self, excess, demand, uom):
        """Aviso de la fila que hace superar la demanda."""
        return _("Exceeds the demand (%(demand)s %(uom)s) by %(excess)s.",
                 demand=formatLang(self.env, demand, dp='Product Unit'), uom=uom.display_name,
                 excess=formatLang(self.env, excess, dp='Product Unit'))

    @api.model
    def _prepare_lot_import_line_vals_arthome(self, valid_rows, default_vals, context_data, product, line_uom, apply=False):
        loc_dest = self.env['stock.location'].browse(default_vals['location_dest_id'])
        dim = self._get_lot_import_dim_arthome(valid_rows)
        vals_list = []
        for row in valid_rows:
            putaway_loc_dest = loc_dest._get_putaway_strategy(product, row['quantity'])
            vals = {
                **default_vals,
                'lot_name': row['lot_name'],
                'quantity': row['quantity'],
                'location_dest_id': putaway_loc_dest.id,
                'product_uom_id': line_uom.id,
            }
            if row['comment']:
                vals['pending_lot_note'] = row['comment']
            if dim:
                vals['x_dim_number'] = dim
            vals_list.append(vals)
        if not apply:
            return vals_list
        picking_type = self.env['stock.picking.type'].browse(default_vals.get('picking_type_id'))
        if picking_type and (picking_type.use_existing_lots or context_data.get('force_lot_m2o')):
            self._create_lot_ids_from_move_line_vals(vals_list, product.id, default_vals.get('company_id'))
            self._apply_lot_import_notes_arthome(vals_list)
        return self._format_lot_import_line_vals_arthome(vals_list)

    @api.model
    def _get_lot_import_dim_arthome(self, valid_rows):
        return next((row['dim'] for row in reversed(valid_rows) if row['dim']), '')

    @api.model
    def _apply_lot_import_notes_arthome(self, vals_list):
        lot_ids_by_note = {}
        for vals in vals_list:
            note = vals.pop('pending_lot_note', False)
            if note and vals.get('lot_id'):
                lot_ids_by_note.setdefault(note, []).append(vals['lot_id'])
                vals['lot_note'] = note
        for note, lot_ids in lot_ids_by_note.items():
            self.env['stock.lot'].browse(lot_ids).write({'note_plain': note})

    @api.model
    def _format_lot_import_line_vals_arthome(self, vals_list):
        move_line_fields = self.env['stock.move.line']._fields
        m2o_keys = {
            key for vals in vals_list for key in vals
            if key in move_line_fields and move_line_fields[key].type == 'many2one'
        }
        display_names = {}
        for key in m2o_keys:
            comodel = self.env[move_line_fields[key].comodel_name]
            ids = {vals[key] for vals in vals_list if isinstance(vals.get(key), int) and vals[key]}
            display_names[key] = {record.id: record.display_name for record in comodel.browse(ids)}
        for vals in vals_list:
            for key in m2o_keys:
                value = vals.get(key)
                if isinstance(value, int) and value:
                    vals[key] = {'id': value, 'display_name': display_names[key].get(value, '')}
        return vals_list
