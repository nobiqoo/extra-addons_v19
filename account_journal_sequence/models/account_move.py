# -*- coding: utf-8 -*-

import time
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    name = fields.Char('Number',
                       readonly=False,
                       copy=False,
                       default='/')

    @api.depends('posted_before', 'state', 'journal_id', 'date', 'move_type', 'origin_payment_id')
    def _compute_name(self):
        self.filtered(lambda m: not m.name and not m.quick_edit_mode).name = '/'
        self._inverse_name()

    def _get_sequence(self):
        '''
            Return the sequence to be used during the post of the current move.
            :return: An ir.sequence record or False.
        '''
        self.ensure_one()

        journal = self.journal_id
        if self.move_type in ('entry', 'out_invoice',
                              'in_invoice', 'out_receipt', 'in_receipt') \
                or not journal.refund_sequence:
            return journal.sequence_id
        if not journal.refund_sequence_id:
            return
        return journal.refund_sequence_id

    def _post(self, soft=True):
        if soft:
            future_moves = self.filtered(
                lambda move: move.date > fields.Date.context_today(self))
            to_post = self - future_moves
        else:
            to_post = self

        for move in to_post:
            if not move.name or move.name == '/':
                # Get the journal's sequence.
                sequence = move._get_sequence()
                if not sequence:
                    raise UserError(
                        _('Defina una secuencia en el diario "%s".',
                          move.journal_id.name))

                # Consume a new number.
                # to_post['name']
                # El core de ir.sequence._next() espera un datetime
                # (hace dt.replace(tzinfo=None)); move.date es un date,
                # por lo que lo convertimos para evitar el TypeError.
                seq_date = (
                    datetime.combine(move.date, datetime.min.time())
                    if move.date else fields.Datetime.now())
                retries = 5
                for attempt in range(retries):
                    try:
                        move.name = sequence.with_context(
                            ir_sequence_date=seq_date).next_by_id()
                        break
                    except Exception as e:
                        if "could not serialize access" in str(e) and attempt < retries - 1:
                            time.sleep(0.1 * (attempt + 1))
                            continue
                        raise

        return super(AccountMove, self)._post(soft)
