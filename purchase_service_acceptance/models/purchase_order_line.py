# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    service_acceptance_line_ids = fields.One2many(
        comodel_name='purchase.service.acceptance.line',
        inverse_name='purchase_line_id',
        string='Service Acceptance Lines',
    )
    qty_pending_reception = fields.Float(
        string='Pending Reception Qty',
        compute='_compute_qty_pending_reception',
        digits='Product Unit of Measure',
        help='Ordered quantity still not covered by an accepted Service Acceptance line.',
    )
    amount_committed = fields.Monetary(
        string='Committed Amount',
        compute='_compute_pyg_amounts',
        currency_field='currency_id',
        help='Ordered but not yet received: a purchase commitment, not yet an accounting expense.',
    )
    amount_service_received = fields.Monetary(
        string='Received, Not Yet Billed',
        compute='_compute_pyg_amounts',
        currency_field='currency_id',
        help='Received (executed) but not yet billed by the vendor: not yet an accounting expense.',
    )
    amount_service_invoiced = fields.Monetary(
        string='Billed Amount',
        compute='_compute_pyg_amounts',
        currency_field='currency_id',
        help='Already billed by the vendor: a real accounting expense.',
    )

    @api.depends('product_qty', 'qty_received')
    def _compute_qty_pending_reception(self):
        for line in self:
            line.qty_pending_reception = max(line.product_qty - line.qty_received, 0.0)

    @api.depends('product_qty', 'qty_received', 'qty_invoiced', 'price_unit')
    def _compute_pyg_amounts(self):
        """Splits the line's value into the three P&L-relevant buckets asked
        for by the ARGOS spec (§11): Compromiso / Servicio Recibido / Gasto.
        Purely informational (quantity x price) — no accounting entries are
        created; the real accounting expense is still recognized natively
        only when the vendor bill posts."""
        for line in self:
            line.amount_committed = max(line.product_qty - line.qty_received, 0.0) * line.price_unit
            line.amount_service_received = max(line.qty_received - line.qty_invoiced, 0.0) * line.price_unit
            line.amount_service_invoiced = line.qty_invoiced * line.price_unit

    def _get_service_acceptance_qty_accepted(self, exclude_line=None):
        """Sum of qty_accepted validated (state 'done') for this PO line,
        across all its service acceptance lines, optionally excluding one
        line."""
        self.ensure_one()
        domain = [
            ('purchase_line_id', '=', self.id),
            ('acceptance_id.state', '=', 'done'),
        ]
        if exclude_line:
            domain.append(('id', '!=', exclude_line.id))
        acceptance_lines = self.env['purchase.service.acceptance.line'].search(domain)
        return sum(acceptance_lines.mapped('qty_accepted'))

    def _get_service_acceptance_qty_pending(self):
        self.ensure_one()
        return max(self.product_qty - self._get_service_acceptance_qty_accepted(), 0.0)
