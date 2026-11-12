# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_mass_confirm(self):
        """Confirma en lote las cotizaciones válidas y muestra el resumen de las omitidas."""
        confirmed = self.browse()
        skipped = []
        for order in self:
            if order.state not in ('draft', 'sent'):
                skipped.append((order, _("It is not a quotation.")))
                continue
            if not order.show_confirm_button:
                skipped.append((order, _("You are not allowed to confirm this quotation.")))
                continue
            try:
                with self.env.cr.savepoint():
                    order.action_confirm()
                confirmed |= order
            except UserError as error:
                skipped.append((order, error.args[0]))
        result = self.env['sale.order.mass.confirm'].create({
            'confirmed_order_ids': [(6, 0, confirmed.ids)],
            'line_ids': [(0, 0, {'order_id': order.id, 'reason': reason}) for order, reason in skipped],
        })
        return {
            'name': _("Confirm Quotations"),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.mass.confirm',
            'res_id': result.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_invoice_grouping_keys(self):
        keys = super()._get_invoice_grouping_keys()
        if self.env.context.get('webflor_invoice_grouping'):
            keys = [key for key in keys if key != 'partner_shipping_id'] + ['webflor_invoice_number']
        return keys

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals['webflor_invoice_number'] = self.webflor_invoice_number
        return vals

    def _create_invoices(self, grouped=False, final=False, date=None):
        webflor_orders = self.filtered('webflor_invoice_number')
        if grouped or not webflor_orders:
            return super()._create_invoices(grouped=grouped, final=final, date=date)
        moves = self.env['account.move']
        other_orders = (self - webflor_orders).with_context(raise_if_nothing_to_invoice=False)
        if other_orders:
            moves |= super(SaleOrder, other_orders)._create_invoices(grouped=grouped, final=final, date=date)
        webflor_orders = webflor_orders.with_context(raise_if_nothing_to_invoice=False, webflor_invoice_grouping=True)
        moves |= super(SaleOrder, webflor_orders)._create_invoices(grouped=grouped, final=final, date=date)
        if not moves and self.env.context.get('raise_if_nothing_to_invoice', True):
            raise UserError(self._nothing_to_invoice_error_message())
        return moves
