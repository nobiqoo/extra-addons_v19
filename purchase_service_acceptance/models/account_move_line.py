# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.constrains('quantity', 'purchase_line_id')
    def _check_service_acceptance_over_invoicing(self):
        """Block a vendor bill/refund line for more Service quantity than has
        actually been received through its Service Acceptance(s) so far —
        checked as soon as the line is saved, even while the bill is still a
        draft, not only when it gets posted.

        `purchase.order.line.qty_invoiced` already counts every non-cancelled
        invoice line (draft included, per native `_prepare_qty_invoiced`), so
        it already reflects this very line's own quantity once saved — no
        need to add anything on top, just compare it against qty_received."""
        prec = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        po_lines = self.mapped('purchase_line_id').filtered(lambda l: l.product_id.type == 'service')
        for po_line in po_lines:
            if float_compare(po_line.qty_invoiced, po_line.qty_received, precision_digits=prec) > 0:
                raise ValidationError(_(
                    'Cannot bill "%s": %s already billed but only %s has been received so far. '
                    'Validate the corresponding Service Acceptance before billing more.',
                    po_line.product_id.display_name, po_line.qty_invoiced, po_line.qty_received,
                ))
