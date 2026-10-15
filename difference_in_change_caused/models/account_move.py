# -*- coding: utf-8 -*-
from odoo import fields, models

class AccountMove(models.Model):
    _inherit = "account.move"

    exchange_id = fields.Many2one(
        'difference.in.change.maker',
        string="Exchange"
    )
    exchange_state = fields.Selection(
        related='exchange_id.state',
    )

    def _reverse_moves(self, default_values_list=None, cancel=False):
        reverse_moves = super()._reverse_moves(default_values_list, cancel)
        
        if self.env.context.get('from_exchange_reversal'):
            for move in reverse_moves:
                if move.ifrs_type and move.reversed_entry_id:
                    reversed_move = move.reversed_entry_id
                    
                    rev_by_account = {
                        rl.account_id.id: rl
                        for rl in reversed_move.line_ids
                    }

                    updates = []
                    for line in move.line_ids:
                        rline = rev_by_account.get(line.account_id.id)
                        if not rline:
                            continue

                        updates.append((1, line.id, {
                            'ifrs_debit':  rline.ifrs_credit,
                            'ifrs_credit': rline.ifrs_debit,
                        }))

                    if updates:
                        move.with_context(check_move_validity=False, skip_readonly_check=True).write({
                            'line_ids': updates,
                        })

                    move.exchange_id = reversed_move.exchange_id
        else:
            # Para reversiones normales
            for move in reverse_moves:
                if move.reversed_entry_id and move.reversed_entry_id.exchange_id:
                    move.exchange_id = move.reversed_entry_id.exchange_id
                    
        return reverse_moves

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    amount_to_exchange = fields.Float(
        digits='Account',
        default=0,
        string="Amount to exchange",
    )
    current_exchange_rate = fields.Float(
        string='Current exchange rate',
        default=1
    )