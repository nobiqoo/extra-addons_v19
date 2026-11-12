# -*- coding: utf-8 -*-

import base64
import io
from collections import defaultdict

import xlsxwriter

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import formatLang

from ..models.stock_move import _normalize_text

PICKING_LOT_IMPORT_HEADER_KEYWORDS = ('referencia', 'reference', 'codigo', 'code')


class StockPickingLotImport(models.TransientModel):
    _name = 'stock.picking.lot.import'
    _description = 'Import Serial/Lot Numbers in a Transfer'

    picking_id = fields.Many2one('stock.picking', ondelete='cascade')
    purchase_import_id = fields.Many2one('purchase.import', ondelete='cascade')
    import_file = fields.Binary(string='File')
    import_file_name = fields.Char(string='File Name')
    lot_text = fields.Text(
        string='Or paste the rows',
        help='Rows copied from the template, in the same column order.',
    )
    keep_lines = fields.Boolean(
        string='Keep current lines',
        help='Add the imported lots to the current lines instead of replacing the lines of the imported products.',
    )
    line_ids = fields.One2many('stock.picking.lot.import.line', 'wizard_id', string='Preview')
    valid_count = fields.Integer(readonly=True)
    error_count = fields.Integer(readonly=True)
    warning_count = fields.Integer(readonly=True)
    previewed = fields.Boolean(readonly=True)
    template_file = fields.Binary(readonly=True)
    template_file_name = fields.Char(readonly=True)

    @api.onchange('import_file', 'lot_text', 'keep_lines')
    def _onchange_import_data(self):
        self.update({'previewed': False, 'line_ids': [Command.clear()], 'valid_count': 0, 'error_count': 0,
                     'warning_count': 0})

    def _get_source_moves(self):
        """Movimientos de la transferencia o, desde Importaciones, los de su pestaña Productos."""
        self.ensure_one()
        return self.picking_id.move_ids if self.picking_id else self.purchase_import_id.moves_ids

    def _get_importable_moves(self):
        return self._get_source_moves().filtered('display_import_lot')

    def _get_lot_import_columns(self):
        if self.purchase_import_id:
            return ('order', 'code', 'product', 'lot_name', 'quantity', 'comment', 'dim', 'picking')
        return ('code', 'product', 'lot_name', 'quantity', 'comment', 'dim')

    def _read_row_values(self, cells):
        """Valores de la fila por nombre de columna."""
        columns = self._get_lot_import_columns()
        cells = [str(cell) for cell in cells] + [''] * len(columns)
        values = {'order': '', 'picking': ''}
        values.update({column: cells[index].strip() for index, column in enumerate(columns)})
        return values

    @api.model
    def _sort_target_moves(self, moves):
        return moves.sorted(lambda move: (
            move.picking_id.state != 'assigned', move.picking_id.scheduled_date or fields.Datetime.now(), move.id))

    def _get_company(self):
        return self.picking_id.company_id or self.purchase_import_id.company_id

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _('Import Serial/Lot Numbers'),
            # Desde Importaciones la vista previa trae orden y recepción: se abre más ancha.
            'context': {'dialog_size': 'extra-large'} if self.purchase_import_id else {},
        }

    def action_download_template(self):
        self.ensure_one()
        moves = self._get_importable_moves()
        if not moves:
            if self.purchase_import_id:
                raise UserError(_("This import has no products that use lots/serial numbers to import."))
            raise UserError(_("This transfer has no products that use lots/serial numbers to import."))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(_('Lots'))
        header = workbook.add_format({'bold': True, 'bg_color': '#714B67', 'font_color': '#FFFFFF'})
        text = workbook.add_format({'num_format': '@'})
        if self.purchase_import_id:
            self._write_purchase_template(sheet, moves, header, text)
        else:
            headers = [_('Reference'), _('Product'), _('Lot/Serial'), _('Quantity'), _('Traceability Note'), _('DIM')]
            for col, title in enumerate(headers):
                sheet.write(0, col, title, header)
            for row, move in enumerate(moves, start=1):
                demand = formatLang(self.env, move.product_uom_qty, dp='Product Unit')
                sheet.write_string(row, 0, move.product_id.default_code or '', text)
                sheet.write_string(row, 1, _('%(product)s (demand %(demand)s %(uom)s)',
                                             product=move.product_id.name, demand=demand, uom=move.product_uom.name))
                sheet.write_string(row, 5, move.x_dim_number or '', text)
            for col, width in enumerate((14, 45, 22, 12, 40, 18)):
                sheet.set_column(col, col, width, text if col in (0, 2, 5) else None)
        sheet.freeze_panes(1, 0)
        workbook.close()
        self.write({
            'template_file': base64.b64encode(output.getvalue()),
            'template_file_name': _('lots_%s.xlsx', (self.picking_id or self.purchase_import_id).name.replace('/', '_')),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/template_file/{self.template_file_name}?download=true',
            'target': 'download',
        }

    def _write_purchase_template(self, sheet, moves, header, text):
        headers = [_('Purchase Order'), _('Reference'), _('Product'), _('Lot/Serial'), _('Quantity'),
                   _('Traceability Note'), _('DIM'), _('Receipt'), _('Pending to Receive')]
        for col, title in enumerate(headers):
            sheet.write(0, col, title, header)
        moves_by_key = defaultdict(lambda: self.env['stock.move'])
        for move in moves:
            moves_by_key[move.purchase_line_id.order_id, move.product_id] |= move
        keys = sorted(moves_by_key, key=lambda key: (key[0].name or '', key[1].default_code or '', key[1].id))
        for row, key in enumerate(keys, start=1):
            order, product = key
            key_moves = moves_by_key[key]
            uom = key_moves[0].product_uom
            pending = sum(move.product_uom._compute_quantity(move.product_uom_qty, uom, round=False)
                          for move in key_moves)
            sheet.write_string(row, 0, order.name or '', text)
            sheet.write_string(row, 1, product.default_code or '', text)
            sheet.write_string(row, 2, product.name or '')
            sheet.write_string(row, 6, next((dim for dim in key_moves.mapped('x_dim_number') if dim), ''), text)
            sheet.write_string(row, 8, '%s %s' % (formatLang(self.env, pending, dp='Product Unit'), uom.name))
        for col, width in enumerate((16, 14, 40, 22, 12, 40, 18, 18, 22)):
            sheet.set_column(col, col, width, text if col in (0, 1, 3, 6, 7) else None)

    def action_preview(self):
        self.ensure_one()
        self._run_import(apply=False)
        return self._reopen()

    def action_import(self):
        self.ensure_one()
        result = self._run_import(apply=True)
        if not result['valid']:
            raise UserError(_("There are no valid lines to import."))
        message = _("%(valid)s lines imported.", valid=len(result['valid']))
        if self.error_count:
            message = _("%(valid)s lines imported, %(errors)s rows rejected.",
                        valid=len(result['valid']), errors=self.error_count)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'warning' if self.error_count else 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _run_import(self, apply):
        if not self.import_file and not (self.lot_text or '').strip():
            raise UserError(_("Upload a file or paste the lots and quantities to import."))
        Move = self.env['stock.move']
        rows = Move._read_lot_import_rows_arthome({
            'file_content': self.import_file,
            'file_name': self.import_file_name,
            'lot_text': self.lot_text,
        })
        if rows and self._is_header(rows[0][1]):
            rows = rows[1:]
        result = self._validate_rows(rows)
        if apply and result['valid']:
            self._apply_rows(result['valid'])
        self._write_preview(result)
        return result

    def _is_header(self, cells):
        values = self._read_row_values(cells)
        return (
            any(keyword in _normalize_text(values['code']) for keyword in PICKING_LOT_IMPORT_HEADER_KEYWORDS)
            and self.env['stock.move']._parse_lot_import_quantity_arthome(values['quantity']) is None
        )

    def _build_move_index(self):
        """Índices en memoria (orden, referencia) → movimientos, armados una sola vez."""
        source_moves = self._get_source_moves()
        importable_ids = set(self._get_importable_moves().ids)
        by_purchase = bool(self.purchase_import_id)
        index = {
            'open': defaultdict(lambda: self.env['stock.move']),
            'source': defaultdict(lambda: self.env['stock.move']),
            'open_orders': defaultdict(lambda: self.env['purchase.order']),
            'orders': {},
        }
        for move in source_moves:
            code = (move.product_id.default_code or '').strip().upper()
            if not code:
                continue
            order = move.purchase_line_id.order_id if by_purchase else self.env['purchase.order']
            index['source'][order.id, code] |= move
            index['source'][False, code] |= move
            if move.id in importable_ids:
                index['open'][order.id, code] |= move
                index['open'][False, code] |= move
                index['open_orders'][code] |= order
            if order:
                index['orders'][order.name.strip().upper()] = order
        return index

    def _resolve_row_moves(self, values, index):
        """Movimientos destino de la fila según la orden de compra, la referencia y la recepción."""
        code = values['code'].upper()
        if not code:
            return False, _("Missing product reference.")
        if (False, code) not in index['source']:
            return False, (_("The product reference is not in this import.") if self.purchase_import_id
                           else _("The product reference is not in this transfer."))
        orders = index['orders']
        order = self.env['purchase.order']
        if self.purchase_import_id:
            if values['order']:
                order = orders.get(values['order'].upper())
                if not order:
                    return False, _("The purchase order %(order)s does not belong to the import %(purchase_import)s.",
                                    order=values['order'], purchase_import=self.purchase_import_id.name)
                if (order.id, code) not in index['source']:
                    return False, _("The product %(product)s is not in the order %(order)s.",
                                    product=values['code'], order=order.name)
            elif len(orders) == 1:
                order = next(iter(orders.values()))
            else:
                candidates = index['open_orders'][code]
                if values['picking']:
                    candidates = candidates.filtered(lambda o: any(
                        move.picking_id.name.upper() == values['picking'].upper()
                        for move in index['open'][o.id, code]))
                if len(candidates) > 1:
                    return False, _("Indicate the purchase order; the product is in several orders (%(orders)s).",
                                    orders=', '.join(sorted(candidates.mapped('name'))))
                order = candidates
            values['order'] = order.name or values['order']
        moves = index['open'].get((order.id if self.purchase_import_id else False, code))
        if not moves:
            source = index['source'].get((order.id, code)) or index['source'][False, code]
            if self.purchase_import_id and any(move.has_tracking != 'none' for move in source):
                return False, _("The receipt of the order %(order)s is not pending.",
                                order=order.name or ', '.join(source.purchase_line_id.order_id.mapped('name')))
            return False, (_("This product does not use lots/serial numbers to import in this import.")
                           if self.purchase_import_id
                           else _("This product does not use lots/serial numbers to import in this transfer."))
        if values['picking']:
            moves = moves.filtered(lambda move: move.picking_id.name.upper() == values['picking'].upper())
            if not moves:
                return False, _("The receipt %(picking)s is not a pending receipt of this product in the order "
                                "%(order)s.", picking=values['picking'], order=order.name)
        return moves, False

    def _validate_rows(self, rows):
        """Valida las filas en memoria y las reparte en los movimientos de su orden de compra."""
        Move = self.env['stock.move']
        index = self._build_move_index()
        valid, errors = [], []
        rows_by_code = defaultdict(list)
        values_by_row = {}
        for row_number, cells in rows:
            values = self._read_row_values(cells)
            values_by_row[row_number] = values
            moves, reason = self._resolve_row_moves(values, index)
            if reason:
                errors.append(dict(self._error_vals(row_number, values), reason=reason))
                continue
            lot_cells = [values['lot_name'], values['quantity'], values['comment'], values['dim']]
            rows_by_code[values['code'].upper()].append((row_number, lot_cells, moves))

        for code, product_rows in rows_by_code.items():
            rows_by_moves = defaultdict(list)
            for row_number, lot_cells, moves in product_rows:
                rows_by_moves[moves].append((row_number, lot_cells))
            parsed, product_errors = [], []
            for moves, group_rows in rows_by_moves.items():
                tracking = moves[0].has_tracking
                line_uom = moves[0].product_uom if tracking == 'lot' else moves[0].product_id.uom_id
                group_parsed, group_errors = Move._parse_lot_import_rows_arthome(group_rows, tracking, line_uom)
                parsed += [dict(row, moves=moves, line_uom=line_uom) for row in group_parsed]
                product_errors += group_errors
            # Lotes repetidos y existentes se revisan por producto: el lote es único por producto.
            parsed.sort(key=lambda row: row['row'])
            product_moves = index['open'][False, code]
            current_lines = [
                {'lot_name': line.lot_name or line.lot_id.name, 'quantity': line.quantity,
                 'product_uom_id': line.product_uom_id.id}
                for line in product_moves.move_line_ids
            ] if self.keep_lines else []
            first_uom = parsed[0]['line_uom'] if parsed else product_moves[0].product_uom
            parsed = Move._validate_lot_import_rows_arthome(
                parsed, product_errors,
                {'product_id': product_moves[0].product_id.id, 'company_id': self._get_company().id},
                {'keep_lines': self.keep_lines, 'current_lines': current_lines, 'demand': 0.0},
                first_uom, first_uom)
            accepted_by_moves = defaultdict(list)
            for row in parsed:
                accepted_by_moves[row['moves']].append(row)
            for moves, group_rows in accepted_by_moves.items():
                accepted, demand_errors = self._allocate_demand(group_rows, moves, group_rows[0]['line_uom'])
                product_errors += demand_errors
                valid += accepted
            errors += [
                dict(self._error_vals(error['row'], values_by_row[error['row']]), reason=error['reason'])
                for error in product_errors
            ]
        return {'valid': valid, 'errors': errors}

    @api.model
    def _error_vals(self, row_number, values):
        return {'row': row_number, 'order': values['order'], 'code': values['code'], 'lot_name': values['lot_name'],
                'quantity': values['quantity'], 'comment': values['comment'], 'dim': values['dim']}

    def _allocate_demand(self, rows, moves, line_uom):
        """Reparte las filas en los movimientos de una misma orden y producto, avisando el exceso."""
        moves = self._sort_target_moves(moves)
        free_by_move = {}
        for move in moves:
            # Las líneas reservadas sin lote se reemplazan al importar: no ocupan demanda.
            used = sum(
                line.product_uom_id._compute_quantity(line.quantity, move.product_uom, round=False)
                for line in move.move_line_ids if line.lot_id or line.lot_name
            ) if self.keep_lines else 0.0
            free_by_move[move] = move.product_uom_qty - used
        uom = moves[0].product_uom
        total_demand = sum(moves.mapped('product_uom_qty'))
        running = total_demand - sum(free_by_move.values())
        accepted = []
        for row in rows:
            qty = line_uom._compute_quantity(row['quantity'], uom, round=False)
            target = next((move for move in moves if move.product_uom.compare(qty, free_by_move[move]) <= 0), moves[-1])
            free_by_move[target] -= qty
            running += qty
            if uom.compare(running, total_demand) > 0:
                row = dict(row, warning=self.env['stock.move']._get_lot_import_excess_warning_arthome(
                    min(qty, running - total_demand), total_demand, uom))
            accepted.append(dict(row, move=target))
        return accepted, []

    def _apply_rows(self, rows):
        """Crea las líneas de los lotes: reemplaza las de cada orden y producto o, al conservar, solo las sin lote."""
        Move = self.env['stock.move']
        rows_by_move = defaultdict(list)
        for row in rows:
            rows_by_move[row['move']].append(row)
        lines = self.env['stock.move'].concat(*{row['moves'] for row in rows}).move_line_ids
        if self.keep_lines:
            lines = lines.filtered(lambda line: not line.lot_id and not line.lot_name)
        lines.unlink()
        vals_list = []
        for move, move_rows in rows_by_move.items():
            product = move.product_id
            line_uom = move_rows[0]['line_uom']
            move_vals = Move._prepare_lot_import_line_vals_arthome(
                move_rows,
                {
                    'move_id': move.id,
                    'picking_id': move.picking_id.id,
                    'product_id': product.id,
                    'company_id': move.company_id.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                },
                {}, product, line_uom, apply=False)
            if move.picking_type_id.use_existing_lots:
                Move._create_lot_ids_from_move_line_vals(move_vals, product.id, move.company_id.id)
                Move._apply_lot_import_notes_arthome(move_vals)
            vals_list += move_vals
        line_fields = self.env['stock.move.line']._fields
        vals_list = [{key: value for key, value in vals.items() if key in line_fields} for vals in vals_list]
        # El DIM queda en los movimientos de cada orden y producto: gana el último de sus filas.
        dims_by_moves = {}
        for row in rows:
            if row['dim']:
                dims_by_moves[row['moves']] = row['dim']
        for moves, dim in dims_by_moves.items():
            moves.x_dim_number = dim
        for vals in vals_list:
            vals.pop('x_dim_number', None)
        self.env['stock.move.line'].create(vals_list)

    def _write_preview(self, result):
        line_cmds = [Command.clear()]
        for row in result['valid']:
            line_cmds.append(Command.create({
                'row': row['row'],
                'order_name': row['move'].purchase_line_id.order_id.name if self.purchase_import_id else False,
                'picking_id': row['move'].picking_id.id,
                'code': row['move'].product_id.default_code,
                'product_id': row['move'].product_id.id,
                'lot_name': row['lot_name'],
                'quantity': row['quantity_text'],
                'comment': row['comment'],
                'dim': row['dim'],
                'status': 'valid',
                'reason': row.get('warning', False),
            }))
        products_by_code = {
            product.default_code.strip().upper(): product.id
            for product in self._get_source_moves().product_id if product.default_code
        }
        for error in sorted(result['errors'], key=lambda e: e['row']):
            line_cmds.append(Command.create({
                'row': error['row'],
                'order_name': error['order'] or False,
                'code': error['code'],
                'product_id': products_by_code.get(error['code'].upper(), False),
                'lot_name': error['lot_name'],
                'quantity': error['quantity'],
                'comment': error['comment'],
                'dim': error['dim'],
                'status': 'error',
                'reason': error['reason'],
            }))
        self.write({
            'line_ids': line_cmds,
            'valid_count': len(result['valid']),
            'error_count': len(result['errors']),
            'warning_count': len([row for row in result['valid'] if row.get('warning')]),
            'previewed': True,
        })


class StockPickingLotImportLine(models.TransientModel):
    _name = 'stock.picking.lot.import.line'
    _description = 'Import Serial/Lot Numbers in a Transfer: Preview Line'
    _order = 'status desc, row'

    wizard_id = fields.Many2one('stock.picking.lot.import', required=True, ondelete='cascade')
    row = fields.Integer()
    order_name = fields.Char(string='Purchase Order')
    picking_id = fields.Many2one('stock.picking', string='Receipt')
    code = fields.Char(string='Reference')
    product_id = fields.Many2one('product.product', string='Product')
    lot_name = fields.Char(string='Lot/Serial')
    quantity = fields.Char()
    comment = fields.Char(string='Traceability Note')
    dim = fields.Char(string='DIM')
    status = fields.Selection([('valid', 'Valid'), ('error', 'Rejected')])
    reason = fields.Char()
