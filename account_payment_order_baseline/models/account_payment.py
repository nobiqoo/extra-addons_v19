# -*- coding: utf-8 -*-

from odoo import _, api, models
from odoo.exceptions import UserError

from .account_move import _ORDER_STATE_AUTH, _reconcile_lock_enabled


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _get_default_journal(self):
        res = super()._get_default_journal()
        return res.filtered(lambda journal: not journal.inbound_payment_order_only)

    @api.model_create_multi
    def create(self, vals_list):
        order_authorized = (
            self.env.su
            or self.env.context.get("allow_order_state_write") is _ORDER_STATE_AUTH
        )
        if not order_authorized:
            for vals in vals_list:
                if not vals.get("payment_order_id"):
                    continue
                order = self.env["account.payment.order"].browse(
                    vals["payment_order_id"]
                )
                if vals.get("company_id"):
                    payment_company = self.env["res.company"].browse(vals["company_id"])
                elif vals.get("journal_id"):
                    payment_company = self.env["account.journal"].browse(
                        vals["journal_id"]
                    ).company_id
                else:
                    payment_company = None
                if (
                    _reconcile_lock_enabled(order.company_id)
                    or _reconcile_lock_enabled(payment_company)
                ):
                    raise UserError(_(
                        "A payment cannot be linked to a payment order "
                        "on creation."
                    ))
        clean_context = {
            key: value for key, value in self.env.context.items()
            if key != "default_payment_order_id"
        }
        return super(AccountPayment, self.with_context(clean_context)).create(vals_list)

    def _generate_journal_entry(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        # OCA's own override (account_payment_order/models/account_payment.py)
        # propagates the already-authorized payment_order_id link onto the
        # freshly generated move right after super() returns here. That
        # write would otherwise hit account_move.py's write() guard,
        # because posting an individual order-linked payment manually
        # (e.g. from the Payments list, instead of going through
        # generated2uploaded()) does not carry allow_order_state_write.
        # The link itself was already legitimately established when the
        # payment was created (guarded at create() time, R28/R29), so
        # completing it here only finishes an already-authorized
        # relationship — it never introduces a new one (R32-L1).
        with_order = self.filtered(lambda payment: payment.payment_order_id)
        without_order = self - with_order
        # Core _generate_journal_entry() has no return value (it writes
        # move_id/state onto self), so neither branch needs to combine a
        # result — just make sure both subsets go through, each with the
        # correct authorization context.
        if with_order:
            super(AccountPayment, with_order.with_context(
                allow_order_state_write=_ORDER_STATE_AUTH
            ))._generate_journal_entry(
                write_off_line_vals=write_off_line_vals,
                force_balance=force_balance,
                line_ids=line_ids,
            )
        if without_order:
            super(AccountPayment, without_order)._generate_journal_entry(
                write_off_line_vals=write_off_line_vals,
                force_balance=force_balance,
                line_ids=line_ids,
            )

    def write(self, vals):
        if (
            "payment_order_id" in vals
            and not self.env.su
            and self.env.context.get("allow_order_state_write") is not _ORDER_STATE_AUTH
        ):
            if vals.get("company_id"):
                target_company = self.env["res.company"].browse(vals["company_id"])
            elif vals.get("journal_id"):
                target_company = self.env["account.journal"].browse(
                    vals["journal_id"]
                ).company_id
            else:
                target_company = None
            protected = self.filtered(
                lambda payment: _reconcile_lock_enabled(payment.company_id)
                or _reconcile_lock_enabled(target_company)
            )
            if protected:
                raise UserError(_(
                    "The linked payment order of a payment cannot be "
                    "changed directly."
                ))
        return super().write(vals)
