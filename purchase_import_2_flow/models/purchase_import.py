# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class PurchaseImport(models.Model):
    _inherit = 'purchase.import'

    def action_validate(self):
        self.ensure_one()
        self.action_moves()
        self.action_lines()

        pending = self.pickings_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
        )
        if pending:
            raise UserError(_(
                "Aún no se ha realizado el ingreso de la mercancía, "
                "comuníquese con inventarios para la recepción de la "
                "mercancía: %s"
            ) % ", ".join(pending.mapped("name")))

        return self._finalize_validate()

    def _finalize_validate(self):
        for record in self.filtered(lambda r: r.state == "confirm"):
            pending = record.pickings_ids.filtered(
                lambda p: p.state not in ("done", "cancel")
            )
            if pending:
                continue

            moves_ids = record.pickings_ids.move_ids.account_move_id
            moves_ids.write({"state": "draft"})
            moves_ids.write({"date": fields.Date.today()})
            for move in moves_ids:
                move.action_post()

            record.action_done()
