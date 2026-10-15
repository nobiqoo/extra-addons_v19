from odoo import models

from .account_move import _RECEIVABLE_PAYABLE_TYPES


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def unlink(self):
        move_model = self.env["account.move"]
        lines = self.mapped("debit_move_id") | self.mapped("credit_move_id")
        if (
            lines.company_id.filtered("restrict_paid_document_unreconcile")
            and not move_model._is_reconcile_draft_authorized()
        ):
            relevant_lines = lines.filtered(
                lambda line: line.account_id.account_type in _RECEIVABLE_PAYABLE_TYPES
            )
            if relevant_lines:
                # Block every partial in a connected reconciliation group if
                # it contains a protected payment source, including indirect
                # links — but only starting the expansion from the
                # receivable/payable pairing (invoice<->payment), never from
                # an unrelated bank-reconciliation line of the same move.
                blockers = relevant_lines._all_reconciled_lines().move_id.filtered(
                    lambda move: move._is_payment_source_move()
                )
                if blockers:
                    raise move_model._reconcile_lock_error(blockers, lines.move_id[:1])
        return super().unlink()
