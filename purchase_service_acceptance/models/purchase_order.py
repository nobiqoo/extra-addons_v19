# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, format_list


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    service_acceptance_ids = fields.One2many(
        comodel_name='purchase.service.acceptance',
        inverse_name='purchase_order_id',
        string='Service Acceptances',
    )
    service_acceptance_count = fields.Integer(
        string='Service Acceptance Count',
        compute='_compute_service_acceptance_count',
    )
    service_reception_status = fields.Selection(
        selection=[
            ('not_started', 'Not Received'),
            ('partial', 'Partially Received'),
            ('full', 'Fully Received'),
        ],
        string='Service Reception Status',
        compute='_compute_service_reception_status',
        help='Reception progress of this order\'s Service lines, based on the '
             'quantities accepted through their Service Acceptances.',
    )

    def _compute_service_acceptance_count(self):
        for order in self:
            order.service_acceptance_count = len(order.service_acceptance_ids)

    @api.depends('order_line.product_id.type', 'order_line.display_type',
                 'order_line.product_qty', 'order_line.qty_received')
    def _compute_service_reception_status(self):
        prec = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            service_lines = order.order_line.filtered(
                lambda line: not line.display_type and line.product_id.type == 'service'
            )
            if not service_lines:
                order.service_reception_status = False
            elif all(float_compare(line.qty_received, 0.0, precision_digits=prec) <= 0 for line in service_lines):
                order.service_reception_status = 'not_started'
            elif all(
                float_compare(line.qty_received, line.product_qty, precision_digits=prec) >= 0
                for line in service_lines
            ):
                order.service_reception_status = 'full'
            else:
                order.service_reception_status = 'partial'

    def button_cancel(self):
        orders_with_accepted_service = self.filtered(
            lambda po: any(
                acceptance.state not in ('draft', 'cancelled') for acceptance in po.service_acceptance_ids
            )
        )
        if orders_with_accepted_service:
            raise UserError(_(
                "Unable to cancel purchase order(s): %s since they have Service "
                "Acceptances that are no longer in draft.",
                format_list(self.env, orders_with_accepted_service.mapped('display_name')),
            ))
        result = super().button_cancel()
        # Mirrors purchase_stock.button_cancel(), which cancels non-done
        # pickings but blocks (above) when a picking is already done: here,
        # draft acceptances (no accounting impact yet) get cancelled along
        # with the order, keeping a trace — unlike the manual "Cancel" action
        # on a draft acceptance, which just deletes it.
        self.service_acceptance_ids.filtered(lambda a: a.state == 'draft').write({'state': 'cancelled'})
        return result

    def button_approve(self, force=False):
        result = super().button_approve(force=force)
        # Some orders in `self` may not have actually been approved yet
        # (e.g. blocked by an approval workflow) — only act on the ones
        # that really reached the 'purchase'/'done' state.
        self.filtered(lambda order: order.state in ('purchase', 'done'))._create_service_acceptance()
        return result

    def _create_service_acceptance(self):
        """Create a draft Service Acceptance covering every Service order line
        that is not yet referenced by any acceptance line of this order.
        Safe to call more than once (e.g. after adding service lines to an
        already confirmed order): it only picks up the lines still missing.
        """
        for order in self:
            existing_purchase_line_ids = order.service_acceptance_ids.filtered(
                lambda a: a.state != 'cancelled'
            ).line_ids.purchase_line_id.ids
            service_lines = order.order_line.filtered(
                lambda line: not line.display_type
                and line.product_id.type == 'service'
                and line.id not in existing_purchase_line_ids
            )
            if service_lines:
                self.env['purchase.service.acceptance'].with_context(skip_qty_accepted_check=True).create({
                    'purchase_order_id': order.id,
                    'line_ids': [(0, 0, {'purchase_line_id': line.id}) for line in service_lines],
                })

    def action_update_service_acceptances(self):
        self._create_service_acceptance()
        return self.action_view_service_acceptance()

    def action_view_service_acceptance(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Service Acceptances'),
            'res_model': 'purchase.service.acceptance',
            'view_mode': 'list,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id},
        }
        if self.service_acceptance_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.service_acceptance_ids.id
        return action
