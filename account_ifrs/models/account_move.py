# -*- coding: utf-8 -*-

from contextlib import ExitStack, contextmanager
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import (
    format_amount,
    SQL,
)


class AccountMove(models.Model):
    _inherit = 'account.move'

    ifrs_type = fields.Selection(
        selection=[
            ('both', 'Both'),
            ('local', 'Local'),
            ('ifrs', 'IFRS'),
        ],
        string='IFRS Type',
        default='both',
        index=True
    )
    has_ifrs_group = fields.Boolean('Has IFRS group',
                                    compute='_compute_has_ifrs_group',
                                    default=lambda self: self.env.user.has_group('account_ifrs.group_account_ifrs'))

    def _compute_has_ifrs_group(self):
        for record in self:
            record.has_ifrs_group = self.env.user.has_group('account_ifrs.group_account_ifrs')

    @contextmanager
    def _check_balanced(self, container):
        ''' Assert the move is fully balanced debit = credit.
        An error is raised if it's not the case.
        '''
        with self._disable_recursion(container, 'check_move_validity', default=True, target=False) as disabled:
            yield
            if disabled:
                return

        if unbalanced_moves := self._get_unbalanced_moves_ifrs(container):
            ifrs = {
                'both': 'AMBOS',
                'ifrs': 'NIIF',
                'local': 'LOCAL',
            }
            error_msg = _("Ha ocurrido un error.\n")
            for move_id, ifrs_type, debit, credit, balance, ifrs_debit, ifrs_credit, ifrs_balance in unbalanced_moves:
                move = self.browse(move_id)
                error_msg += (
                    "El asiento (%s) está desbalanceado o sus apuntes no se ajustan al tipo %s.\n\n"
                    ">> Parte LOCAL:\n"
                    "- Débito: %s\n"
                    "- Crédito: %s\n"
                    "- Balance: %s\n\n"
                    ">> Parte NIIF:\n"
                    "- Débito: %s\n"
                    "- Crédito: %s\n"
                    "- Balance: %s\n") % (
                    move.display_name, ifrs.get(ifrs_type, 'Ambos'),
                    format_amount(self.env, debit or 0, move.company_id.currency_id),
                    format_amount(self.env, credit or 0, move.company_id.currency_id),
                    format_amount(self.env, balance or 0, move.company_id.currency_id),
                    format_amount(self.env, ifrs_debit or 0, move.company_id.currency_id),
                    format_amount(self.env, ifrs_credit or 0, move.company_id.currency_id),
                    format_amount(self.env, ifrs_balance or 0, move.company_id.currency_id))
            raise UserError(error_msg)

    def _get_unbalanced_moves_ifrs(self, container):
        moves = container['records'].filtered(lambda move: move.line_ids)
        if not moves:
            return 
        # super(AccountMove, self)._get_unbalanced_moves(container)

        # /!\ As this method is called in create / write, we can't make the assumption the computed stored fields
        # are already done. Then, this query MUST NOT depend on computed stored fields.
        # It happens as the ORM calls create() with the 'no_recompute' statement.
        self.env['account.move.line'].flush_model(['debit', 'credit', 'balance', 'ifrs_debit', 'ifrs_credit', 'ifrs_balance', 'ifrs_type', 'currency_id', 'move_id'])
        self.env['account.move'].flush_model(['ifrs_type', 'company_id'])
        unbalanced_moves = self.env.execute_query(SQL('''
            SELECT 
                move.id AS move_id,
                move.ifrs_type,
                ROUND(SUM(line.debit), currency.decimal_places) AS debit,
                ROUND(SUM(line.credit), currency.decimal_places) AS credit,
                ROUND(SUM(line.balance), currency.decimal_places) AS balance,
                ROUND(SUM(line.ifrs_debit), currency.decimal_places) AS ifrs_debit,
                ROUND(SUM(line.ifrs_credit), currency.decimal_places) AS ifrs_credit,
                ROUND(SUM(line.ifrs_balance), currency.decimal_places) AS ifrs_balance
            FROM account_move_line line
            JOIN account_move move ON move.id = line.move_id
            JOIN res_company company ON company.id = move.company_id
            JOIN res_currency currency ON currency.id = company.currency_id
            WHERE line.move_id IN %s
            GROUP BY move.id, move.ifrs_type, currency.decimal_places
            HAVING (
                -- Caso 1: Local => ifrs_* deben ser 0 y balance local debe cuadrar
                (move.ifrs_type = 'local' AND (
                    ROUND(SUM(line.ifrs_debit), currency.decimal_places) != 0 OR
                    ROUND(SUM(line.ifrs_credit), currency.decimal_places) != 0 OR
                    ROUND(SUM(line.ifrs_balance), currency.decimal_places) != 0 OR
                    ROUND(SUM(line.balance), currency.decimal_places) != 0
                ))
                OR
                -- Caso 2: IFRS => local deben ser 0 y balance NIIF debe cuadrar
                (move.ifrs_type = 'ifrs' AND (
                    ROUND(SUM(line.debit), currency.decimal_places) != 0 OR
                    ROUND(SUM(line.credit), currency.decimal_places) != 0 OR
                    ROUND(SUM(line.balance), currency.decimal_places) != 0 OR
                    ROUND(SUM(line.ifrs_balance), currency.decimal_places) != 0
                ))
                OR
                -- Caso 3: Ambos => ambas contabilidades deben cuadrar
                (move.ifrs_type = 'both' AND (
                    ROUND(SUM(line.balance), currency.decimal_places) != 0 OR
                    ROUND(SUM(line.ifrs_balance), currency.decimal_places) != 0 OR
                    ROUND(SUM(line.debit), currency.decimal_places) != ROUND(SUM(line.ifrs_debit), currency.decimal_places) OR
                    ROUND(SUM(line.credit), currency.decimal_places) != ROUND(SUM(line.ifrs_credit), currency.decimal_places)
                ))
            )
        ''', tuple(moves.ids)))
        return unbalanced_moves


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    _sql_constraints = [
        (
            'check_ifrs_credit_debit',
            'CHECK(ifrs_credit + ifrs_debit >= 0 AND ifrs_credit * ifrs_debit = 0)',
            'Wrong IFRS credit or IFRS debit value in accounting entry !'
        ),
    ]

    ifrs_type = fields.Selection(
        related='move_id.ifrs_type',
        store=True,
        index=True
    )
    ifrs_debit = fields.Monetary(
        string='IFRS Debit',
        currency_field='company_currency_id',
        compute='_compute_ifrs',
        inverse='_inverse_ifrs',
        store=True
    )
    ifrs_credit = fields.Monetary(
        string='IFRS Credit',
        currency_field='company_currency_id',
        compute='_compute_ifrs',
        inverse='_inverse_ifrs',
        store=True
    )
    ifrs_balance = fields.Monetary(
        string='IFRS Balance',
        currency_field='company_currency_id',
        compute='_compute_ifrs_balance',
        store=True,
    )

    @api.depends('ifrs_type', 'debit', 'credit')
    def _compute_ifrs(self):
        self = self.with_context(check_move_validity=False)
        for line in self:
            if line.ifrs_type == 'local':
                line.ifrs_debit = 0.0
                line.ifrs_credit = 0.0
            elif line.ifrs_type == 'ifrs':
                line.ifrs_debit = line.debit
                line.ifrs_credit = line.credit
                line.debit = 0.0
                line.credit = 0.0
            else:  # both
                line.ifrs_debit = line.debit
                line.ifrs_credit = line.credit

    def _inverse_ifrs(self):
        for line in self:
            if line.ifrs_type == 'ifrs':
                line.debit = 0.0
                line.credit = 0.0

    @api.depends('ifrs_debit', 'ifrs_credit')
    def _compute_ifrs_balance(self):
        for line in self:
            line.ifrs_balance = line.ifrs_debit - line.ifrs_credit
