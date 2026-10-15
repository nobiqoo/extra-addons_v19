from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super().action_post()
        Mapping = self.env['sale.picking.invoice.mapping'].sudo()
        for move in self.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund')):
            try:
                Mapping.ensure_mappings_for_invoice(
                    move, force=False, apply_to_lines=True
                )
            except Exception:
                _logger.exception(
                    "[MAPPING] Error creando mapeo al publicar %s", move.name)
        return res