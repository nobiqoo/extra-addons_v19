# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_slip_applicable = fields.Boolean(
        compute='_compute_delivery_slip_applicable',
        exportable=False,
        help='Technical field: the transfer comes from a sale order and is a delivery or an internal step (pick/pack).',
    )
    box_count_applicable = fields.Boolean(
        compute='_compute_box_count_applicable',
        exportable=False,
        help='Technical field: the transfer comes from a sale order and is a delivery or a dropship.',
    )
    box_count = fields.Integer(
        string='Box Count',
        default=0,
        copy=False,
        tracking=True,
        help='Number of boxes of the delivery, typed by the warehouse user. The sale order shows the sum of its '
             'deliveries that are not cancelled.',
    )
    line_count_applicable = fields.Boolean(
        compute='_compute_line_count_applicable',
        exportable=False,
        help='Technical field: the transfer comes from a sale order and is a delivery, a dropship or an internal '
             'step (pick/pack).',
    )
    line_count = fields.Integer(
        string='Line Count',
        compute='_compute_line_count',
        store=True,
        help='Number of distinct lots/serial numbers per product in the detailed operations. A product without '
             'lot, or not reserved yet, counts as 1.',
    )
    delivery_weight = fields.Float(
        string='Total Weight',
        digits='Stock Weight',
        compute='_compute_delivery_weight',
        help='Product weight multiplied by the demanded quantity, or by the done quantity once the transfer is done. '
             'Products without weight count as 0.',
    )
    delivery_weight_uom_name = fields.Char(
        string='Weight Unit of Measure',
        compute='_compute_delivery_weight_uom_name',
    )
    insurable_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Insurable Value Currency',
        compute='_compute_insurable_currency_id',
        store=True,
    )
    insurable_value = fields.Monetary(
        string='Insurable Value',
        currency_field='insurable_currency_id',
        compute='_compute_insurable_value',
        store=True,
        readonly=False,
        copy=False,
        help='Configured percentage (Inventory settings) of the sale order net unit price multiplied by the '
             'quantities of this transfer. It can be edited; it is recomputed when the quantities change.',
    )

    lot_import_applicable = fields.Boolean(
        compute='_compute_lot_import_applicable',
        exportable=False,
        help='Technical field: the transfer has products whose lots/serial numbers can be imported.',
    )
    order_info_applicable = fields.Boolean(
        compute='_compute_order_info_applicable',
        exportable=False,
        help='Technical field: the transfer comes from a sale order or a point of sale order and is a delivery '
             'or an internal step (pick/pack).',
    )
    order_reference = fields.Char(
        string='Order Number',
        compute='_compute_order_info',
        compute_sudo=True,
        help='Sale order, or point of sale receipt, that originated the transfer.',
    )
    salesperson_name = fields.Char(
        string='Salesperson',
        compute='_compute_order_info',
        compute_sudo=True,
        help='Salesperson of the sale order, or cashier of the point of sale order.',
    )
    delivery_comment = fields.Text(
        string='Dispatch Note/Instruction',
        compute='_compute_delivery_comment',
        compute_sudo=True,
        store=True,
        readonly=False,
        copy=True,
        tracking=True,
        help='Copied from the sale order, or from the general customer note of the point of sale order, when the '
             'transfer is created. Editing the order updates the open transfers that still have its previous text; '
             'done transfers keep the text they were processed with. It can be adjusted on open deliveries.',
    )

    _box_count_positive = models.Constraint(
        'CHECK(box_count >= 0)',
        'The box count cannot be negative.',
    )

    @api.depends('move_ids.display_import_lot')
    def _compute_lot_import_applicable(self):
        for picking in self:
            picking.lot_import_applicable = any(picking.move_ids.mapped('display_import_lot'))

    def action_open_lot_import_arthome(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Serial/Lot Numbers'),
            'res_model': 'stock.picking.lot.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_picking_id': self.id},
        }

    @api.depends('sale_id', 'pos_order_id', 'picking_type_code')
    def _compute_order_info_applicable(self):
        for picking in self:
            picking.order_info_applicable = bool(picking.sale_id or picking.pos_order_id) \
                and picking.picking_type_code in ('outgoing', 'internal')

    @api.depends('sale_id.name', 'sale_id.user_id.name',
                 'pos_order_id.pos_reference', 'pos_order_id.cashier')
    def _compute_order_info(self):
        for picking in self:
            if picking.sale_id:
                order = picking.sale_id
                picking.order_reference = order.name
                picking.salesperson_name = order.user_id.name
            else:
                pos_order = picking.pos_order_id
                picking.order_reference = pos_order.pos_reference or pos_order.name
                picking.salesperson_name = pos_order.cashier

    @api.depends()
    def _compute_delivery_comment(self):
        for picking in self:
            picking.delivery_comment = picking.sale_id.delivery_comment or picking.pos_order_id.general_customer_note

    @api.model
    def _propagate_delivery_comment(self, order_field, previous_comments, new_comment):
        pickings = self.sudo().search([
            (order_field, 'in', list(previous_comments)),
            ('state', 'not in', ('done', 'cancel')),
        ])
        pickings.filtered(
            lambda picking: (picking.delivery_comment or '') == (previous_comments[picking[order_field].id] or '')
        ).delivery_comment = new_comment

    @api.depends('sale_id', 'picking_type_code')
    def _compute_delivery_slip_applicable(self):
        for picking in self:
            picking.delivery_slip_applicable = bool(picking.sale_id) and picking.picking_type_code in ('outgoing', 'internal')

    @api.depends('sale_id', 'picking_type_code')
    def _compute_box_count_applicable(self):
        for picking in self:
            picking.box_count_applicable = bool(picking.sale_id) and picking.picking_type_code in ('outgoing', 'dropship')

    @api.depends('sale_id', 'picking_type_code')
    def _compute_line_count_applicable(self):
        for picking in self:
            picking.line_count_applicable = bool(picking.sale_id) \
                and picking.picking_type_code in ('outgoing', 'internal', 'dropship')

    @api.depends('sale_id', 'picking_type_id', 'move_ids', 'move_ids.state', 'move_ids.product_id',
                 'move_line_ids', 'move_line_ids.product_id', 'move_line_ids.lot_id', 'move_line_ids.lot_name')
    def _compute_line_count(self):
        """Cuenta los lotes distintos por producto; las líneas sin lote y los productos sin reservar cuentan 1."""
        applicable = self.filtered(lambda picking: picking._origin and picking.line_count_applicable)
        lots_by_product = defaultdict(set)
        if applicable:
            picking_ids = applicable._origin.ids
            # El lote se identifica por lot_id o, si aún no existe (se crea al validar), por lot_name;
            # las operaciones sin lote del producto forman un solo grupo
            for picking, product, lot, lot_name in self.env['stock.move.line']._read_group(
                [('picking_id', 'in', picking_ids)], ['picking_id', 'product_id', 'lot_id', 'lot_name'],
            ):
                lots_by_product[picking.id, product.id].add(lot.id or lot_name or False)
            # Productos de movimientos sin operaciones detalladas
            for picking, product in self.env['stock.move']._read_group(
                [('picking_id', 'in', picking_ids), ('state', '!=', 'cancel')], ['picking_id', 'product_id'],
            ):
                lots = lots_by_product[picking.id, product.id]
                if not lots:
                    lots.add(False)
        counts = defaultdict(int)
        for (picking_id, _product_id), lots in lots_by_product.items():
            counts[picking_id] += len(lots)
        for picking in self:
            picking.line_count = counts[picking._origin.id] if picking in applicable else 0

    @api.depends('state', 'move_ids.state', 'move_ids.product_id', 'move_ids.product_uom',
                 'move_ids.product_uom_qty', 'move_ids.quantity')
    def _compute_delivery_weight(self):
        weights = defaultdict(float)
        pickings = self.filtered('id')
        if pickings:
            groups = self.env['stock.move']._read_group(
                [('picking_id', 'in', pickings.ids), ('state', '!=', 'cancel')],
                ['picking_id', 'product_id', 'product_uom'],
                ['product_uom_qty:sum', 'quantity:sum'],
            )
            for picking, product, uom, demand_qty, done_qty in groups:
                qty = done_qty if picking.state == 'done' else demand_qty
                weights[picking.id] += uom._compute_quantity(qty, product.uom_id, round=False) * product.weight
        for picking in self:
            picking.delivery_weight = weights[picking.id]

    def _compute_delivery_weight_uom_name(self):
        uom_name = self.env['product.template']._get_weight_uom_name_from_ir_config_parameter()
        for picking in self:
            picking.delivery_weight_uom_name = uom_name

    @api.depends('sale_id.currency_id', 'company_id.currency_id')
    def _compute_insurable_currency_id(self):
        """Usa la moneda del pedido de venta o, si no hay pedido, la de la compañía."""
        for picking in self:
            picking.insurable_currency_id = picking.sale_id.currency_id or picking.company_id.currency_id

    @api.depends('sale_id', 'picking_type_code', 'state', 'move_ids.state', 'move_ids.product_uom',
                 'move_ids.product_uom_qty', 'move_ids.quantity', 'move_ids.sale_line_id.price_reduce_taxexcl')
    def _compute_insurable_value(self):
        """Aplica el porcentaje asegurable al precio neto de venta por las cantidades de la transferencia."""
        applicable = self.filtered('delivery_slip_applicable')
        (self - applicable).insurable_value = 0.0
        for picking in applicable:
            total = 0.0
            for move in picking.move_ids:
                sale_line = move.sale_line_id
                if move.state == 'cancel' or not sale_line or sale_line.product_id != move.product_id:
                    continue
                qty = move.quantity if picking.state == 'done' else move.product_uom_qty
                sale_qty = move.product_uom._compute_quantity(qty, sale_line.product_uom_id, round=False)
                total += sale_qty * sale_line.price_reduce_taxexcl
            percentage = picking.company_id.insurable_value_percentage
            picking.insurable_value = picking.insurable_currency_id.round(total * percentage / 100.0)
