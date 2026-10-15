from odoo import _, api, models
from odoo.exceptions import UserError

from .account_move import (
    _UNRECONCILE_AUTH,
    _VOUCHER_LINK_AUTH,
    _reconcile_lock_enabled,
)


class AccountVoucher(models.Model):
    _inherit = "account.voucher"

    @api.ondelete(at_uninstall=False)
    def _unlink_except_locked_source(self):
        # account.move.voucher_id has ondelete='cascade': deleting a posted
        # voucher would silently cascade-delete its journal entry (and its
        # reconciliations) at the database level, bypassing button_draft()
        # and account.partial.reconcile.unlink() entirely. Force the
        # legitimate action_cancel() flow instead, same as every other
        # guard in this module. Protection is judged from EITHER the
        # voucher's own company OR its linked move's company, since the two
        # can differ if move_id was forged across companies (R29).
        #
        # Also cover the orphaned case (L1): action_draft() can clear
        # voucher.move_id while the move's own voucher_id still points
        # back, so a posted move can outlive the voucher<->move_id link on
        # the voucher side. Search for any posted move still referencing
        # this voucher, not only the voucher's own current move_id.
        # sudo(): a multi-company record rule would otherwise only surface
        # moves in the session's currently active companies, letting a
        # user with just one company active miss a posted move living in
        # a different (but still protected) company (R31-L2).
        orphaned_posted = self.env["account.move"].sudo().search([
            ("voucher_id", "in", self.ids),
            ("state", "=", "posted"),
        ])
        orphaned_by_voucher = {m.voucher_id.id: m for m in orphaned_posted}
        for voucher in self:
            blocking_move = voucher.move_id
            if not (blocking_move and blocking_move.state == "posted"):
                blocking_move = orphaned_by_voucher.get(voucher.id)
            if blocking_move and (
                _reconcile_lock_enabled(voucher.company_id)
                or _reconcile_lock_enabled(blocking_move.company_id)
            ):
                raise UserError(_(
                    "You cannot delete voucher '%s' while its journal entry "
                    "is posted. Cancel it first."
                ) % voucher.display_name)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                move_id = vals.get("move_id")
                target_move_company = (
                    self.env["account.move"].browse(move_id).company_id
                    if move_id else None
                )
                company = self.env["res.company"].browse(
                    vals.get("company_id")
                    or self.env.context.get("default_company_id")
                    or self.env.company.id
                )
                protected = (
                    _reconcile_lock_enabled(company)
                    or _reconcile_lock_enabled(target_move_company)
                )
                if not protected:
                    continue
                if move_id:
                    raise UserError(_(
                        "The linked journal entry of a voucher cannot be set "
                        "on creation."
                    ))
                if vals.get("state", "draft") != "draft":
                    raise UserError(_(
                        "A voucher must be created in draft state."
                    ))
        clean_context = {
            key: value for key, value in self.env.context.items()
            if key not in ("default_move_id", "default_state")
        }
        return super(AccountVoucher, self.with_context(clean_context)).create(vals_list)

    def write(self, vals):
        if (
            ("move_id" in vals or "state" in vals)
            and not self.env.su
            and self.env.context.get("allow_voucher_link_write") is not _VOUCHER_LINK_AUTH
        ):
            target_company = (
                self.env["res.company"].browse(vals["company_id"])
                if vals.get("company_id") else None
            )
            target_move_company = (
                self.env["account.move"].browse(vals["move_id"]).company_id
                if vals.get("move_id") else None
            )
            protected = self.filtered(
                lambda voucher: _reconcile_lock_enabled(voucher.company_id)
                or (voucher.move_id and _reconcile_lock_enabled(voucher.move_id.company_id))
                or _reconcile_lock_enabled(target_company)
                or _reconcile_lock_enabled(target_move_company)
            )
            if protected:
                raise UserError(_(
                    "The linked journal entry or state of a voucher cannot be "
                    "changed directly."
                ))
        return super().write(vals)

    def action_post(self):
        return super(AccountVoucher, self.with_context(
            allow_voucher_link_write=_VOUCHER_LINK_AUTH
        )).action_post()

    def action_draft(self):
        if not self.env.su:
            protected = self.filtered(
                lambda voucher: _reconcile_lock_enabled(voucher.company_id)
                or (voucher.move_id and _reconcile_lock_enabled(voucher.move_id.company_id))
            )
            if protected.filtered(lambda voucher: voucher.state != "cancel"):
                raise UserError(_(
                    "You can only reset to draft vouchers that are in cancel state."
                ))
        return super(AccountVoucher, self.with_context(
            allow_voucher_link_write=_VOUCHER_LINK_AUTH
        )).action_draft()

    def action_cancel(self):
        linked = self.filtered(lambda voucher: voucher.move_id)
        # Gated by the flag (either side's company) rather than fully
        # unconditional (L2): legacy/migrated vouchers whose move_id link
        # predates this ticket's bookkeeping could have a mismatched
        # voucher_id in companies that never opted into this feature, and
        # those must keep working exactly as before. The R29 cross-company
        # attack still requires the LINKED move to be in a protected
        # company, so checking "either company protected" still catches it
        # (the unprotected-company voucher pointing at a protected-company
        # move is protected via move_id.company_id).
        protected_linked = linked.filtered(
            lambda voucher: _reconcile_lock_enabled(voucher.company_id)
            or _reconcile_lock_enabled(voucher.move_id.company_id)
        )
        inconsistent = protected_linked.filtered(
            lambda voucher: voucher.move_id.voucher_id != voucher
        )
        if inconsistent:
            raise UserError(_(
                "Cannot cancel voucher(s) %s: the linked journal entry "
                "does not point back to this voucher."
            ) % ", ".join(inconsistent.mapped("display_name")))
        posted = linked.filtered(lambda voucher: voucher.move_id.state == "posted")
        # Protection is judged from the MOVE's own company, not the
        # voucher's — this is the other half of the R29 fix.
        protected_posted = posted.filtered(
            lambda voucher: _reconcile_lock_enabled(voucher.move_id.company_id)
        )
        if protected_posted and not (
            self.env.su or self.env.user.has_group("account.group_account_user")
        ):
            raise UserError(_(
                "You are not allowed to cancel posted vouchers."
            ))
        unauthorized = self - posted
        result = True
        if posted:
            result = super(AccountVoucher, posted.with_context(
                allow_locked_payment_draft=_UNRECONCILE_AUTH,
                allow_voucher_link_write=_VOUCHER_LINK_AUTH,
            )).action_cancel()
        if unauthorized:
            result = super(AccountVoucher, unauthorized.with_context(
                allow_voucher_link_write=_VOUCHER_LINK_AUTH
            )).action_cancel()
        return result
