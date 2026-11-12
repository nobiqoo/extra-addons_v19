# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, fields, models

PROPAGATION_FIELDS = {'carrier_partner_id', 'carrier_tracking_number', 'propagate_to_pickings'}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    carrier_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Carrier",
        domain="[('is_carrier', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        copy=False,
        index='btree_not_null',
        tracking=True,
    )
    carrier_tracking_number = fields.Char(string="Tracking Number", copy=False, tracking=True)
    propagate_to_pickings = fields.Boolean(
        string="Propagate to Deliveries",
        help="Copy the carrier and the tracking number to the deliveries of this order when it is confirmed and whenever they change.",
    )

    def write(self, vals):
        res = super().write(vals)
        if PROPAGATION_FIELDS.intersection(vals) and not self.env.context.get('skip_carrier_propagation'):
            self._propagate_carrier_to_pickings()
        return res

    def _action_confirm(self):
        res = super()._action_confirm()
        self._propagate_carrier_to_pickings()
        return res

    def _propagate_carrier_to_pickings(self):
        orders = self.filtered('propagate_to_pickings').sudo()
        pickings_by_values = defaultdict(lambda: self.env['stock.picking'])
        for order in orders:
            values = (order.carrier_partner_id.id, order.carrier_tracking_number)
            pickings_by_values[values] |= order.picking_ids.filtered(
                lambda picking: picking.state != 'cancel'
                and (picking.carrier_partner_id.id, picking.carrier_tracking_number) != values
            )
        for (carrier_id, tracking_number), pickings in pickings_by_values.items():
            if not pickings:
                continue
            pickings.with_context(skip_carrier_sync=True).write({
                'carrier_partner_id': carrier_id,
                'carrier_tracking_number': tracking_number,
            })
            for picking in pickings:
                picking.message_post(body=_("Transportadora y guía tomadas del pedido %s.", picking.sale_id.name))

    def action_open_shipping_report(self):
        """Abre el reporte de información de guías filtrado por los pedidos seleccionados."""
        action = self.env['ir.actions.act_window']._for_xml_id('sale_arthome.action_sale_shipping_report')
        action['domain'] = [('order_id', 'in', self.ids)]
        action['context'] = {}
        return action
