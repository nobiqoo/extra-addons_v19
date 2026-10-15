# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import UserError

_UNRECONCILE_AUTH = object()
_VOUCHER_LINK_AUTH = object()
_ORDER_STATE_AUTH = object()
_RECEIVABLE_PAYABLE_TYPES = ("asset_receivable", "liability_payable")


def _reconcile_lock_enabled(company):
    return bool(company and company.restrict_paid_document_unreconcile)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_payment_order_communication_direct(self):
        """
        **ODONE: Overwrite this method to use the payment reference as communication**
        Retrieve the communication string for this direct item."""
        communication = self.payment_reference or self.ref or self.name
        if self.is_invoice():
            if (self.reference_type or "none") != "none":
                communication = self.ref
            elif self.is_purchase_document():
                communication = self.ref or self.payment_reference
            else:
                communication = self.payment_reference or self.name
        return communication or ""

    def _is_payment_source_move(self):
        self.ensure_one()
        return bool(
            self.company_id.restrict_paid_document_unreconcile
            and self.state == "posted"
            and (
                (self.voucher_id and self.voucher_id.move_id == self)
                or self.payment_order_id
            )
        )

    def _is_reconcile_draft_authorized(self):
        return self.env.context.get("allow_locked_payment_draft") is _UNRECONCILE_AUTH

    def _get_reconcile_lock_blockers(self):
        blockers = self.env["account.move"]
        for move in self:
            if move._is_payment_source_move():
                blockers |= move
            else:
                relevant_lines = move.line_ids.filtered(
                    lambda line: line.account_id.account_type in _RECEIVABLE_PAYABLE_TYPES
                )
                reconciled_moves = relevant_lines._all_reconciled_lines().move_id
                blockers |= reconciled_moves.filtered(
                    lambda candidate: candidate._is_payment_source_move()
                )
        return blockers

    def _reconcile_lock_error(self, blockers, move=None):
        origins = sorted(
            blockers.voucher_id.mapped("display_name")
            + blockers.payment_order_id.mapped("display_name")
        )
        return UserError(_(
            "You cannot unreconcile '%(move)s' directly. It already has a "
            "payment registered from %(origen)s. To undo the reconciliation "
            "you must cancel or reset to draft that source document.",
            move=(move or self[:1]).display_name,
            origen=", ".join(dict.fromkeys(origins)),
        ))

    def button_draft(self):
        if not self._is_reconcile_draft_authorized():
            protected = self.filtered(
                lambda move: move.company_id.restrict_paid_document_unreconcile
            )
            if protected:
                blockers = protected._get_reconcile_lock_blockers()
                if blockers:
                    subject = protected.filtered(
                        lambda move: bool(blockers & move._get_reconcile_lock_blockers())
                    )[:1] or protected[:1]
                    raise self._reconcile_lock_error(blockers, subject)
        return super().button_draft()

    @api.model_create_multi
    def create(self, vals_list):
        order_authorized = (
            self.env.su
            or self.env.context.get("allow_order_state_write") is _ORDER_STATE_AUTH
        )
        if not order_authorized:
            for vals in vals_list:
                if vals.get("payment_order_id"):
                    order = self.env["account.payment.order"].browse(
                        vals["payment_order_id"]
                    )
                    if _reconcile_lock_enabled(order.company_id):
                        raise UserError(_(
                            "A journal entry cannot be linked to a "
                            "payment order on creation."
                        ))
        # Legitimate payment generation passes payment_order_id in vals,
        # never through a context default.
        clean_context = {
            key: value for key, value in self.env.context.items()
            if key != "default_payment_order_id"
        }
        return super(AccountMove, self.with_context(clean_context)).create(vals_list)

    def _reconcile_lock_target_company(self, vals):
        if vals.get("company_id"):
            return self.env["res.company"].browse(vals["company_id"])
        if vals.get("journal_id"):
            return self.env["account.journal"].browse(vals["journal_id"]).company_id
        return None

    def write(self, vals):
        # F1: block forging `state` away from "posted" on a currently-posted
        # protected source move (the same condition button_draft() checks,
        # but enforced directly in write() so it cannot be bypassed by
        # skipping the named button_draft() method).
        if (
            "state" in vals
            and vals.get("state") != "posted"
            and not self.env.su
            and not self._is_reconcile_draft_authorized()
        ):
            protected = self.filtered(
                lambda m: m.state == "posted" and _reconcile_lock_enabled(m.company_id)
            )
            if protected:
                blockers = protected._get_reconcile_lock_blockers()
                if blockers:
                    subject = protected.filtered(
                        lambda m: bool(blockers & m._get_reconcile_lock_blockers())
                    )[:1] or protected[:1]
                    raise self._reconcile_lock_error(blockers, subject)

        target_company = self._reconcile_lock_target_company(vals)
        if "voucher_id" in vals and not self.env.su:
            protected = self.filtered(
                lambda move: _reconcile_lock_enabled(move.company_id)
                or _reconcile_lock_enabled(target_company)
            )
            if protected:
                raise UserError(_(
                    "The linked voucher of a journal entry cannot be "
                    "changed directly."
                ))
        if (
            "payment_order_id" in vals
            and not self.env.su
            and self.env.context.get("allow_order_state_write") is not _ORDER_STATE_AUTH
        ):
            protected = self.filtered(
                lambda move: _reconcile_lock_enabled(move.company_id)
                or _reconcile_lock_enabled(target_company)
            )
            if protected:
                raise UserError(_(
                    "The linked payment order of a journal entry cannot be "
                    "changed directly."
                ))
        return super().write(vals)
