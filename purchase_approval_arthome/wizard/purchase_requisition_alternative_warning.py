# -*- coding: utf-8 -*-

from odoo import models

from ..models.purchase_order import OPEN_ALTERNATIVE_STATES


class PurchaseRequisitionAlternativeWarning(models.TransientModel):
    _inherit = 'purchase.requisition.alternative.warning'

    def _action_done(self):
        return self.po_ids.with_context(skip_alternative_check=True).button_confirm()

    def action_keep_alternatives(self):
        """Confirma las órdenes y registra en el chatter las alternativas que siguen abiertas."""
        res = super().action_keep_alternatives()
        self.po_ids._log_alternatives_summary()
        return res

    def action_cancel_alternatives(self):
        alternatives = self.alternative_po_ids.filtered(
            lambda po: po.state in OPEN_ALTERNATIVE_STATES and po.id not in self.po_ids.ids)
        alternatives._cancel_discarded_alternatives(self.po_ids)
        res = self._action_done()
        self.po_ids._log_alternatives_summary(cancelled=alternatives)
        return res
