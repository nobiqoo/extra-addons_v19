# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    sequence_id = fields.Many2one('ir.sequence',
                        'Secuencia',
                        help='Este campo contiene la información relacionada '
                        'con la numeración de los asientos de este diario.',
                        copy=False)
    sequence_number_next = fields.Integer('Siguiente número',
                        help='El siguiente número de secuencia se utilizará '
                        'para la próxima factura.',
                        compute='_compute_seq_number_next',
                        inverse='_inverse_seq_number_next')
    refund_sequence_id = fields.Many2one('ir.sequence',
                        'Secuencia Nota Crédito',
                        help='Este campo contiene la información relacionada '
                        'con la numeración de las notas '
                        'crédito de este diario.',
                        copy=False)
    refund_sequence_number_next = fields.Integer('Siguiente número NC',
                        help='El siguiente número de secuencia será usará '
                        'para la siguiente nota credito',
                        compute='_compute_refund_seq_number_next',
                        inverse='_inverse_refund_seq_number_next')

    @api.model
    def _create_sequence(self, vals, refund=False):
        ''' Create new no_gap entry sequence for every new Journal'''
        prefix = self._get_sequence_prefix(vals.get('code'), refund)
        seq_name = refund and vals['code'] + _(': Refund') or vals['code']
        seq = {
            'name': _('%s Sequence') % seq_name,
            'implementation': 'no_gap',
            'prefix': prefix,
            'padding': 4,
            'number_increment': 1,
            'use_date_range': True,
        }
        if 'company_id' in vals:
            seq['company_id'] = vals['company_id']
        seq = self.env['ir.sequence'].create(seq)
        seq_date_range = seq._get_current_sequence()
        seq_date_range.number_next = refund \
            and vals.get('refund_sequence_number_next', 1) \
                or vals.get('sequence_number_next', 1)
        return seq

    def create_sequence(self, refund):
        # refund = False
        prefix = self._get_sequence_prefix(self.code, refund)
        seq_name = refund and self.code + _(': Refund') or self.code
        seq = {
            'name': _('%s Sequence') % seq_name,
            'implementation': 'no_gap',
            'prefix': prefix,
            'padding': 4,
            'number_increment': 1,
            'use_date_range': True,
        }
        if self.company_id:
            seq['company_id'] = self.company_id.id
        seq = self.env['ir.sequence'].create(seq)
        seq_date_range = seq._get_current_sequence()
        seq_date_range.number_next = refund \
            and (self.refund_sequence_number_next or 1) \
                or (self.sequence_number_next or 1)
        return seq

    def create_journal_sequence(self):
        if not self.sequence_id:
            seq = self.create_sequence(refund=False)
            self.sequence_id = seq.id
        if not self.refund_sequence_id:
            seq = self.create_sequence(refund=True)
            self.refund_sequence_id = seq.id

    # do not depend on 'sequence_id.date_range_ids', because
    # sequence_id._get_current_sequence() may invalidate it!
    @api.depends('sequence_id.use_date_range',
                 'sequence_id.number_next_actual')
    def _compute_seq_number_next(self):
        '''
        Compute 'sequence_number_next'
         according to the current sequence in use,
         an ir.sequence or an ir.sequence.date_range.
        '''
        for journal in self:
            if journal.sequence_id:
                sequence = journal.sequence_id._get_current_sequence()
                journal.sequence_number_next = sequence.number_next_actual
            else:
                journal.sequence_number_next = 1

    def _inverse_seq_number_next(self):
        '''
        Inverse 'sequence_number_next'
         to edit the current sequence next number.
        '''
        for journal in self:
            if journal.sequence_id and journal.sequence_number_next:
                sequence = journal.sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.sequence_number_next

    # do not depend on 'refund_sequence_id.date_range_ids', because
    # refund_sequence_id._get_current_sequence() may invalidate it!
    @api.depends('refund_sequence_id.use_date_range',
                 'refund_sequence_id.number_next_actual')
    def _compute_refund_seq_number_next(self):
        '''
        Compute 'sequence_number_next'
         according to the current sequence in use,
        an ir.sequence or an ir.sequence.date_range.
        '''
        for journal in self:
            if journal.refund_sequence_id and journal.refund_sequence:
                sequence = journal.refund_sequence_id._get_current_sequence()
                journal.refund_sequence_number_next = \
                    sequence.number_next_actual
            else:
                journal.refund_sequence_number_next = 1

    def _inverse_refund_seq_number_next(self):
        '''
        Inverse 'refund_sequence_number_next'
         to edit the current sequence next number.
        '''
        for journal in self:
            if journal.refund_sequence_id \
                and journal.refund_sequence \
                    and journal.refund_sequence_number_next:
                sequence = journal.refund_sequence_id._get_current_sequence()
                sequence.sudo().number_next = \
                    journal.refund_sequence_number_next

    @api.model
    def _get_sequence_prefix(self, code, refund=False):
        prefix = code.upper()
        if refund:
            prefix = 'R' + prefix
        return prefix + '/%(range_year)s/'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # OVERRIDE
            if not vals.get('sequence_id') and vals.get('code'):
                vals.update({
                    'sequence_id': self.sudo()._create_sequence(vals).id
                })
            if vals.get('type') in ('sale', 'purchase') \
                and vals.get('refund_sequence') \
                    and not vals.get('refund_sequence_id'):
                vals.update({
                    'refund_sequence_id': self.sudo()._create_sequence(
                        vals, refund=True).id
                })
        return super(AccountJournal, self.with_context(
                mail_create_nolog=True)).create(vals_list)

    def write(self, vals):
        for journal in self:
            if ('code' in vals and journal.code != vals['code']):
                if self.env['account.move'].search(
                        [('journal_id', 'in', self.ids)], limit=1):
                    raise UserError(
                        _('This journal already contains items, '
                          'therefore you cannot modify its short name.'))
                new_prefix = self._get_sequence_prefix(
                    vals['code'], refund=False)
                journal.sequence_id.write({'prefix': new_prefix})
                if journal.refund_sequence_id:
                    new_prefix = self._get_sequence_prefix(
                        vals['code'], refund=True)
                    journal.refund_sequence_id.write({'prefix': new_prefix})
            if vals.get('refund_sequence'):
                for journal in self.filtered(
                        lambda j: j.type in (
                            'sale',
                            'purchase'
                        ) and not j.refund_sequence_id):
                    journal_vals = {
                        'name': journal.name,
                        'company_id': journal.company_id.id,
                        'code': journal.code,
                        'refund_sequence_number_next': vals.get(
                            'refund_sequence_number_next',
                            journal.refund_sequence_number_next
                        ),
                    }
                    journal.refund_sequence_id = self.sudo()._create_sequence(
                        journal_vals, refund=True).id
        result = super(AccountJournal, self).write(vals)
        return result
