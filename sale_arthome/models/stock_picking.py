# -*- coding: utf-8 -*-
from odoo import _, fields, models

CARRIER_FIELDS = {'carrier_partner_id', 'carrier_tracking_number'}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    carrier_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Carrier",
        domain="[('is_carrier', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        copy=False,
        tracking=True,
    )
    carrier_tracking_number = fields.Char(string="Tracking Number", copy=False, tracking=True)

    def write(self, vals):
        res = super().write(vals)
        changed = CARRIER_FIELDS.intersection(vals)
        if changed and not self.env.context.get('skip_carrier_sync'):
            self._sync_carrier_to_sale_order(changed)
        return res

    def _sync_carrier_to_sale_order(self, changed):
        orders_by_values = {}
        for picking in self.sudo().filtered('sale_id'):
            order = picking.sale_id
            pending = {}
            for name in changed:
                value = picking[name].id if picking._fields[name].type == 'many2one' else picking[name]
                current = order[name].id if order._fields[name].type == 'many2one' else order[name]
                if value != current:
                    pending[name] = value
            if not pending:
                continue
            key = tuple(sorted(pending.items()))
            orders_by_values.setdefault(key, self.env['sale.order'])
            orders_by_values[key] |= order
            order.message_post(body=_("Transportadora o guía actualizadas desde la entrega %s.", picking.name))
        for key, orders in orders_by_values.items():
            orders.with_context(skip_carrier_propagation=True).write(dict(key))
