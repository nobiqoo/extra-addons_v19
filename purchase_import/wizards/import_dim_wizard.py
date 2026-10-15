# -*- coding: utf-8 -*-

import base64
import io
import csv
import re
import unicodedata

from odoo import models, fields, _
from odoo.exceptions import UserError


def _norm(s):
    """Lowercase + strip accents for header matching."""
    nfkd = unicodedata.normalize('NFD', str(s))
    return nfkd.encode('ascii', 'ignore').decode('ascii').lower().strip()


class ImportDimWizard(models.TransientModel):
    _name = 'import.dim.wizard'
    _description = 'Asistente de Importación DIM'

    file_data = fields.Binary(string='Archivo', required=True)
    file_name = fields.Char(string='Nombre del Archivo')
    result_log = fields.Text(string='Resultado', readonly=True)
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('done', 'Completado')],
        default='draft',
    )

    def _detect_columns(self, headers):
        """Returns dict: picking/product/dim -> column index.

        Handles both manual templates and Odoo native exports:
          - Picking:  'picking_id', 'recep…', 'referencia', 'reference', 'nombre'
          - Product:  'product_id', 'produc…' (excl. uom/qty),
                      'linea de operacion' / 'operations' root (no '/' in header)
          - DIM:      any header containing 'dim'
        """
        mapping = {}
        for i, h in enumerate(headers):
            hn = _norm(h)
            h_raw = h.strip()

            if 'picking' not in mapping:
                if any(k in hn for k in ('recep', 'picking', 'referencia', 'reference', 'nombre')):
                    mapping['picking'] = i

            if 'product' not in mapping:
                is_product_field = ('produc' in hn) and ('uom' not in hn) and ('qty' not in hn)
                # "Línea de operación" root (no sub-path slash) → contains product display_name
                is_moveline_root = (
                    ('linea de operacion' in hn or hn in ('operations', 'operaciones'))
                    and '/' not in h_raw
                )
                if is_product_field or is_moveline_root:
                    mapping['product'] = i

            if 'dim' not in mapping:
                if 'dim' in hn:
                    mapping['dim'] = i

        missing = [k for k in ('picking', 'product', 'dim') if k not in mapping]
        if missing:
            raise UserError(
                _('No se encontraron las columnas requeridas: %s\n'
                  'Encabezados detectados: %s') % (', '.join(missing), ', '.join(headers))
            )
        return mapping

    def _parse_file(self):
        """Returns list of (row_num, picking_name, product_name, dim_value)."""
        if not self.file_data:
            raise UserError(_('Por favor, cargue un archivo.'))

        file_bytes = base64.b64decode(self.file_data)
        fname = (self.file_name or '').lower()

        if fname.endswith('.xlsx') or fname.endswith('.xls'):
            return self._parse_excel(file_bytes)
        return self._parse_csv(file_bytes)

    def _parse_excel(self, file_bytes):
        try:
            import openpyxl
        except ImportError:
            raise UserError(_('La librería openpyxl no está disponible.'))

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            raise UserError(_('El archivo está vacío.'))

        headers = [str(c or '').strip() for c in rows[0]]
        col = self._detect_columns(headers)

        rows_data = []
        last_picking = ''
        for i, row in enumerate(rows[1:], start=2):
            picking_name = str(row[col['picking']] or '').strip()
            product_name = str(row[col['product']] or '').strip()
            dim_value = str(row[col['dim']] or '').strip()

            # carry-forward: native export only fills picking in the first row of each group
            if picking_name:
                last_picking = picking_name
            else:
                picking_name = last_picking

            if not picking_name and not product_name:
                continue
            rows_data.append((i, picking_name, product_name, dim_value))
        return rows_data

    def _parse_csv(self, file_bytes):
        try:
            text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text = file_bytes.decode('latin-1')

        reader = csv.reader(io.StringIO(text))
        all_rows = list(reader)
        if not all_rows:
            raise UserError(_('El archivo está vacío.'))

        headers = [c.strip() for c in all_rows[0]]
        col = self._detect_columns(headers)

        rows_data = []
        last_picking = ''
        for i, row in enumerate(all_rows[1:], start=2):
            if len(row) <= max(col.values()):
                continue
            picking_name = row[col['picking']].strip()
            product_name = row[col['product']].strip()
            dim_value = row[col['dim']].strip()

            if picking_name:
                last_picking = picking_name
            else:
                picking_name = last_picking

            if not picking_name and not product_name:
                continue
            rows_data.append((i, picking_name, product_name, dim_value))
        return rows_data

    def _find_product(self, product_name):
        """Search product handling '[ref] Name' Odoo export format."""
        ref_match = re.match(r'^\[(.+?)\]\s*(.*)', product_name)
        if ref_match:
            ref = ref_match.group(1).strip()
            name_part = ref_match.group(2).strip()
            product = self.env['product.product'].search(
                [('default_code', '=', ref)], limit=1)
            if not product and name_part:
                product = self.env['product.product'].search(
                    [('name', '=', name_part)], limit=1)
        else:
            product = self.env['product.product'].search(
                [('default_code', '=', product_name)], limit=1)
            if not product:
                product = self.env['product.product'].search(
                    [('name', '=', product_name)], limit=1)
        return product

    def action_import(self):
        rows_data = self._parse_file()

        StockMove = self.env['stock.move']
        log_lines = []
        updated = 0
        errors = 0

        for row_num, picking_name, product_name, dim_value in rows_data:
            if not picking_name or not product_name:
                log_lines.append(_('Fila %d: Recepción o Producto vacío — omitida.') % row_num)
                errors += 1
                continue

            picking = self.env['stock.picking'].search([
                ('name', '=', picking_name),
                ('picking_type_code', '=', 'incoming'),
            ], limit=1)
            if not picking:
                log_lines.append(
                    _('Fila %d: Recepción "%s" no encontrada.') % (row_num, picking_name))
                errors += 1
                continue

            product = self._find_product(product_name)
            if not product:
                log_lines.append(
                    _('Fila %d: Producto "%s" no encontrado.') % (row_num, product_name))
                errors += 1
                continue

            move = StockMove.search([
                ('picking_id', '=', picking.id),
                ('product_id', '=', product.id),
                ('state', 'not in', ['draft', 'cancel']),
            ], limit=1)
            if not move:
                log_lines.append(
                    _('Fila %d: No se encontró movimiento para "%s" / "%s".') % (
                        row_num, picking_name, product_name))
                errors += 1
                continue

            move.x_dim_number = dim_value
            log_lines.append(
                _('Fila %d: [OK] %s / %s → DIM = "%s"') % (
                    row_num, picking_name, product_name, dim_value))
            updated += 1

        summary = _('Resultado: %d actualizados, %d errores.\n\n') % (updated, errors)
        self.result_log = summary + '\n'.join(log_lines)
        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
