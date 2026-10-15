# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.tools import SQL


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    authorization_number = fields.Char(
        string='Authorization Number',
        index='btree_not_null',
        help=(
            "Authorization or approval number reported by the bank for this transaction, "
            "as copied from the bank statement (Excel/CSV import or bank connection). It is "
            "used to automatically match this bank statement line with the corresponding "
            "customer payment during the bank reconciliation."
        ),
    )

    def _try_auto_reconcile_statement_lines(self, company_id=None):
        # EXTENDS account_accountant
        # The Authorization Number is a stronger and unambiguous signal than the generic
        # label/amount based matching done by the core engine, so it is applied first.
        # Statement lines resolved by it are removed from the batch before the standard
        # auto-reconciliation logic takes over for the remaining ones.
        reconciled_lines = self._reconcile_by_authorization_number()
        remaining_lines = self - reconciled_lines
        if not remaining_lines:
            return
        return super(AccountBankStatementLine, remaining_lines)._try_auto_reconcile_statement_lines(
            company_id=company_id
        )

    def _reconcile_by_authorization_number(self):
        """ Automatically reconcile the statement lines in `self` with the customer payment
        sharing the exact same Authorization Number, for the companies that enabled this
        matching criterion on at least one active reconciliation model.

        :return: the subset of `self` that got fully reconciled this way.
        """
        candidate_lines = self.filtered(lambda line: line.authorization_number and not line.is_reconciled)
        if not candidate_lines:
            return self.browse()

        enabled_company_ids = set(self.env['account.reconcile.model'].search([
            ('company_id', 'in', candidate_lines.company_id.ids),
            ('active', '=', True),
            ('match_authorization_number', '=', True),
        ]).company_id.ids)
        candidate_lines = candidate_lines.filtered(lambda line: line.company_id.id in enabled_company_ids)
        if not candidate_lines:
            return self.browse()

        # A customer payment/voucher move always has (at least) two lines: the
        # receivable one (reconciled against the invoice) and the liquidity/outstanding
        # one (the one to reconcile against the bank statement). Both are linked to the
        # same payment/voucher, but only the liquidity line has the same balance sign as
        # the statement line amount, which is enough to tell them apart. `account.move`'s
        # own `authorization_number` (computed from the originating payment or voucher,
        # regardless of the source: Accounting, a receipt voucher, or Point of Sale)
        # already carries the value, so a single join to the move is enough. The
        # counterpart lines created for invoice matching are excluded with
        # `voucher_line_id IS NULL`.
        reconcilable_account_ids = self.env['account.account'].search([('reconcile', '=', True)]).ids
        if not reconcilable_account_ids:
            return self.browse()

        self.env.cr.execute(SQL(
            """
            SELECT st_line.id AS st_line_id,
                   ARRAY_AGG(DISTINCT aml.id) AS aml_ids
              FROM account_bank_statement_line st_line
              JOIN account_move_line aml
                ON aml.company_id = st_line.company_id
               AND aml.account_id IN %s
               AND aml.reconciled = false
               AND aml.parent_state = 'posted'
               AND aml.voucher_line_id IS NULL
              JOIN account_move mv
                ON mv.id = aml.move_id
               AND mv.authorization_number = st_line.authorization_number
             WHERE st_line.id IN %s
               AND ((st_line.amount > 0 AND aml.balance > 0) OR (st_line.amount < 0 AND aml.balance < 0))
          GROUP BY st_line.id
            HAVING COUNT(DISTINCT aml.id) = 1
            """,
            tuple(reconcilable_account_ids), tuple(candidate_lines.ids),
        ))

        reconciled_lines = self.browse()
        for st_line_id, aml_ids in self.env.cr.fetchall():
            st_line = self.browse(st_line_id).with_prefetch(self._prefetch_ids)
            aml = self.env['account.move.line'].browse(aml_ids)

            transaction_amount = st_line.amount_currency if st_line.foreign_currency_id else st_line.amount
            transaction_currency = st_line.foreign_currency_id or st_line.currency_id
            residual = aml.amount_residual_currency if aml.currency_id == transaction_currency else aml.amount_residual
            if transaction_currency.compare_amounts(abs(residual), abs(transaction_amount)) != 0:
                # The Authorization Number matches but the amount doesn't: leave it for the
                # accountant to review manually instead of risking a wrong reconciliation.
                continue

            st_line.set_line_bank_statement_line(aml.ids)
            if st_line.currency_id.is_zero(st_line.amount_residual):
                reconciled_lines += st_line

        return reconciled_lines
