import logging
from collections import defaultdict
from datetime import timedelta
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class SalePickingInvoiceMapping(models.Model):
    _name = 'sale.picking.invoice.mapping'
    _description = 'Sale Picking Invoice Mapping'
    _order = 'sale_order_id, picking_sequence, invoice_date'

    sale_order_id = fields.Many2one('sale.order', required=True, index=True)
    picking_id = fields.Many2one('stock.picking', required=True)
    invoice_id = fields.Many2one('account.move', required=True)
    picking_sequence = fields.Integer(string='Picking Sequence')
    invoice_date = fields.Date(related='invoice_id.date', store=True)
    picking_type_code = fields.Selection(
        related='picking_id.picking_type_id.code', store=True)
    invoice_type = fields.Selection(related='invoice_id.move_type', store=True)

    manual = fields.Boolean(
        string='Creado manualmente',
        default=False,
        help='Indica si el mapeo fue creado manualmente'
    )

    @api.model
    def cron_build_mappings_batch(self, batch_size=200, days_back=365, force=False):
        """
        Cron: procesa órdenes de venta por lotes y genera mapping en sale.picking.invoice.mapping.
        - batch_size: cuántas SO procesa por ejecución
        - days_back: cuántos días hacia atrás busca SOs (reduce costo)
        - force: si True, reconstruye mappings para cada factura encontrada
        """
        Mapping = self.env['sale.picking.invoice.mapping'].sudo()
        ICP = self.env['ir.config_parameter'].sudo()

        last_so_id = int(ICP.get_param(
            'sale_picking_invoice_mapping.last_so_id', '0') or 0)

        date_from = fields.Datetime.to_string(
            fields.Datetime.now() - timedelta(days=days_back))

        domain = [
            ('id', '>', last_so_id),
            ('date_order', '>=', date_from),
        ]
        sale_orders = self.env['sale.order'].sudo().search(
            domain, order='id asc', limit=batch_size)

        if not sale_orders:
            ICP.set_param('sale_picking_invoice_mapping.last_so_id', '0')
            _logger.info(
                "[MAPPING CRON] No hay más SO por procesar. Reiniciando puntero a 0.")
            return True

        processed_so = 0
        processed_moves = 0
        created_mappings = 0

        for so in sale_orders:
            processed_so += 1

            moves = self.env['account.move'].sudo().search([
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                '|', ('line_ids.sale_line_ids.order_id', '=', so.id),
                ('invoice_origin', '=', so.name),
            ])

            for mv in moves:
                processed_moves += 1
                try:
                    created_mappings += Mapping.ensure_mappings_for_invoice(
                        mv, force=force, apply_to_lines=True
                    )
                except Exception:
                    _logger.exception(
                        "[MAPPING CRON] Error procesando move %s (SO %s)", mv.name, so.name)

        ICP.set_param('sale_picking_invoice_mapping.last_so_id',
                      str(sale_orders[-1].id))

        _logger.info(
            "[MAPPING CRON] SO procesadas=%s, moves=%s, mappings creados=%s, last_so_id=%s",
            processed_so, processed_moves, created_mappings, sale_orders[-1].id
        )
        return True

    @api.model
    def _get_related_sale_orders_from_invoice(self, move):
        """Detecta SOs relacionados:
        1) Por sale_line_ids en líneas de factura
        2) Por invoice_origin (si viene SO001 o varios separados por coma)
        3) Para NC: por reversed_entry_id si aplica
        """
        sale_orders = self.env['sale.order']

        if move.invoice_line_ids and 'sale_line_ids' in move.invoice_line_ids._fields:
            sale_orders |= move.invoice_line_ids.mapped(
                'sale_line_ids.order_id')

        if not sale_orders and move.invoice_origin:
            names = [x.strip()
                     for x in move.invoice_origin.split(',') if x.strip()]
            if names:
                sale_orders |= self.env['sale.order'].search(
                    [('name', 'in', names)])

        if not sale_orders and move.move_type == 'out_refund' and getattr(move, 'reversed_entry_id', False):
            inv = move.reversed_entry_id
            if inv and inv.invoice_line_ids and 'sale_line_ids' in inv.invoice_line_ids._fields:
                sale_orders |= inv.invoice_line_ids.mapped(
                    'sale_line_ids.order_id')

        return sale_orders

    @api.model
    def _pickings_from_invoice_and_sale_order(self, move, sale_order):
        """Obtiene pickings candidatos basados en vínculo real (sale_line -> stock.move)."""
        if not move.invoice_line_ids or 'sale_line_ids' not in move.invoice_line_ids._fields:
            return self.env['stock.picking']

        sale_lines = move.invoice_line_ids.mapped(
            'sale_line_ids').filtered(lambda sl: sl.order_id == sale_order)
        if not sale_lines:
            return self.env['stock.picking']

        if 'move_ids' not in sale_lines._fields:
            return self.env['stock.picking']

        stock_moves = sale_lines.mapped('move_ids').filtered(
            lambda m: m.state == 'done' and m.picking_id)
        pickings = stock_moves.mapped('picking_id')

        if move.move_type == 'out_invoice':
            pickings = pickings.filtered(
                lambda p: p.picking_type_id.code == 'outgoing' or p.picking_type_id.code == 'dropship')
        elif move.move_type == 'out_refund':
            pickings = pickings.filtered(
                lambda p: p.picking_type_id.code in ('incoming', 'outgoing') or p.picking_type_id.code == 'dropship')
        return pickings.filtered(lambda p: p.state == 'done')

    @api.model
    def ensure_mappings_for_invoice(self, move, force=False, apply_to_lines=True):
        """Crea mapeos faltantes para un move posted.
        - force=True: permite reconstruir mapeos y re-asignar líneas.
        """
        if move.state != 'posted' or move.move_type not in ('out_invoice', 'out_refund'):
            return 0

        sale_orders = self._get_related_sale_orders_from_invoice(move)
        if not sale_orders:
            return 0

        created = self.env['sale.picking.invoice.mapping']
        to_create = []

        for so in sale_orders:
            if force:
                self.search([('sale_order_id', '=', so.id),
                            ('invoice_id', '=', move.id)]).unlink()

            pickings = self._pickings_from_invoice_and_sale_order(move, so)

            if not pickings:
                if move.move_type == 'out_invoice':
                    pickings = so.picking_ids.filtered(
                        lambda p: p.state == 'done' and p.picking_type_id.sequence_code == 'OUT'
                    ).sorted('date_done')
                else:
                    pickings = so.picking_ids.filtered(
                        lambda p: p.state == 'done' and (
                            p.picking_type_id.sequence_code == 'RET' or p.picking_type_id.code == 'incoming'
                        )
                    ).sorted('date_done')

            if not pickings:
                continue

            for idx, picking in enumerate(pickings, start=1):
                exists = self.search([
                    ('sale_order_id', '=', so.id),
                    ('invoice_id', '=', move.id),
                    ('picking_id', '=', picking.id),
                ], limit=1)
                if exists:
                    continue

                to_create.append({
                    'sale_order_id': so.id,
                    'invoice_id': move.id,
                    'picking_id': picking.id,
                    'picking_sequence': idx,
                })

        if to_create:
            created = self.create(to_create)
            _logger.warning("Creados %s mapeos para move %s",
                            len(created), move.name)

        if created and apply_to_lines:
            created._apply_mappings_to_move_lines(force=force)

        return len(created)

    # ----------------------------
    # Aplicación a líneas contables (robusta)
    # ----------------------------

    def _apply_mappings_to_move_lines(self, force=False):
        """Asigna stock_picking_id en líneas de factura con prioridad:
        1) vínculo real: invoice_line.sale_line_ids.move_ids.picking_id
        2) fallback por productos (tu lógica actual)
        No pisa si ya hay stock_picking_id, a menos que force=True.
        """
        _logger.warning(
            "Aplicando mapeos a líneas contables (force=%s)...", force)

        for mapping in self:
            move = mapping.invoice_id
            picking = mapping.picking_id
            if not picking or picking.state != 'done':
                continue

            lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.product_id)
            if not lines:
                continue

            if not force:
                lines = lines.filtered(lambda l: not l.stock_picking_id)
                if not lines:
                    continue

            exact_lines = self.env['account.move.line']
            if 'sale_line_ids' in lines._fields and 'move_ids' in self.env['sale.order.line']._fields:
                for line in lines:
                    sl = line.sale_line_ids
                    if not sl:
                        continue
                    pks = sl.mapped('move_ids').filtered(
                        lambda m: m.state == 'done' and m.picking_id).mapped('picking_id')
                    if picking in pks:
                        exact_lines |= line

            if exact_lines:
                exact_lines.write({'stock_picking_id': picking.id})

            remaining = lines.filtered(
                lambda l: force or not l.stock_picking_id)
            if remaining:
                picking_products = set(
                    picking.move_ids.filtered(
                        lambda m: m.state == 'done' and m.product_id).mapped('product_id').ids
                )
                remaining_to_update = remaining.filtered(
                    lambda l: l.product_id.id in picking_products)
                if remaining_to_update:
                    remaining_to_update.write({'stock_picking_id': picking.id})

        _logger.warning("Finalizó aplicación de mapeos.")

    # ----------------------------
    # Mantener acción masiva
    # ----------------------------

    @api.model
    def create_mappings(self):
        """Server action: crea/llena mapeos para SOs con actividad."""
        _logger.warning("Creando mapeos masivos...")

        sale_orders = self.env['sale.order'].search([
            ('picking_ids', '!=', False),
            '|', ("create_date", ">=", "2025-01-01 00:00:00"),
            ('date_order', '>=', '2025-01-01 00:00:00')
        ])

        total = 0
        for so in sale_orders:
            moves = self.env['account.move'].search([
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                '|', ('line_ids.sale_line_ids.order_id', '=', so.id),
                ('invoice_origin', '=', so.name),
            ])
            for mv in moves:
                total += self.ensure_mappings_for_invoice(
                    mv, force=False, apply_to_lines=True)

        return total


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    picking_invoice_mapping_ids = fields.One2many(
        'sale.picking.invoice.mapping', 'sale_order_id', string='Picking Invoice Mappings'
    )
    picking_invoice_count = fields.Integer(
        string='Mappings Count', compute='_compute_picking_invoice_count'
    )

    @api.depends('picking_invoice_mapping_ids')
    def _compute_picking_invoice_count(self):
        for record in self:
            record.picking_invoice_count = len(
                record.picking_invoice_mapping_ids)

    def create_mapping_button(self):
        """Botón: ruta rápida, pero usando el nuevo motor.
        - Aquí sí tiene sentido usar force=True para “reconstruir”
        """
        self.ensure_one()

        moves = self.env['account.move'].search([
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            '|', ('line_ids.sale_line_ids.order_id', '=', self.id),
            ('invoice_origin', '=', self.name),
        ])

        self.env['sale.picking.invoice.mapping'].search(
            [('sale_order_id', '=', self.id)]).unlink()

        total = 0
        for mv in moves:
            total += self.env['sale.picking.invoice.mapping'].ensure_mappings_for_invoice(
                mv, force=True, apply_to_lines=True
            )

        return total
