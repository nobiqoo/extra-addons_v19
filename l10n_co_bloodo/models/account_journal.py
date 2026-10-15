# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    fiscal_position_local = fields.Boolean('Posición Fiscal Local',
                                           related='company_id.fiscal_position_local',)

    is_einvoicing = fields.Boolean('Fac. electrónica',
                            help='Habilita la opción configurar la '
                            'resolución DIAN para facturación electrónica')
    edi_code = fields.Char('Código corto',
                           size=5,
                           help='Se utiliza para crear el prefijo '
                           'de las secuencias')
    resolution_text = fields.Html('Info de resolución',
                            help='Texto informativo sobre la resolución '
                            'de facturación electrónica que aparecerá en '
                            'la representación gráfica.')
    note_ei = fields.Html('Notas en fac. electrónica',
                          help='Este texto será mostrado en la '
                          'representación gráfica de factura electrónica.')

    debit_note_sequence = fields.Boolean('Secuencia para nota débito',
                        help='Marque esta casilla si no desea compartir la '
                        'misma secuencia para las facturas y notas de '
                        'débito electrónicas realizadas desde este diario.',
                        default=False)
    debit_note_sequence_id = fields.Many2one('ir.sequence',
                        'Secuencia de Nota Débito',
                        help='Este campo contiene la información '
                        'relacionada con la numeración de las notas de '
                        'débito electrónicas de este diario.',
                        copy=False)
    debit_note_sequence_number_next = fields.Integer('Próximo número Nota Débito',
                        help='El siguiente número de secuencia se utilizará para '
                        'la siguiente nota de débito.',
                        compute='_compute_debit_seq_number_next',
                        inverse='_inverse_debit_seq_number_next')

    remaining_numbers = fields.Integer('Números restantes',
                                       default=False)
    remaining_days = fields.Integer('Días restantes',
                                    default=False)
    edi_technical_key = fields.Char('Llave técnica')

    @api.depends('debit_note_sequence_id.use_date_range',
                 'debit_note_sequence_id.number_next_actual')
    def _compute_debit_seq_number_next(self):
        '''
            Compute 'sequence_number_next' according to the
            current sequence in use, an ir.sequence or an
            ir.sequence.date_range.
        '''
        for journal in self:
            if journal.debit_note_sequence_id and journal.debit_note_sequence:
                sequence = \
                    journal.debit_note_sequence_id._get_current_sequence()
                journal.debit_note_sequence_number_next = \
                    sequence.number_next_actual
            else:
                journal.debit_note_sequence_number_next = 1

    def _inverse_debit_seq_number_next(self):
        '''
            Inverse 'debit_note_sequence_number_next'
            to edit the current sequence next number.
        '''
        for journal in self:
            if journal.debit_note_sequence_id \
                and journal.debit_note_sequence \
                    and journal.debit_note_sequence_number_next:
                sequence = \
                    journal.debit_note_sequence_id._get_current_sequence()
                sequence.sudo().number_next = \
                    journal.debit_note_sequence_number_next

    def write(self, vals):
        for journal in self:
            if ('code' in vals and journal.edi_code != vals['code']):
                if self.env['account.move'].search(
                        [('journal_id', 'in', self.ids)], limit=1):
                    raise UserError(
                        _('Este diario ya contiene elementos, por lo tanto,'
                          ' no puede modificar su nombre corto.'))
                if journal.debit_note_sequence_id:
                    new_prefix = self._get_sequence_prefix(
                        vals['code'], refund=False, type_note='debit')
                    journal.debit_note_sequence_id.write(
                        {'prefix': new_prefix})
            if vals.get('debit_note_sequence'):
                for journal in self.filtered(
                    lambda j: j.type in ('sale', 'purchasex') \
                        and not j.debit_note_sequence_id):
                    journal_vals = {
                        'name': journal.name,
                        'company_id': journal.company_id.id,
                        'code': journal.code,
                        'debit_note_sequence_number_next': vals.get(
                            'debit_note_sequence_number_next',
                            journal.debit_note_sequence_number_next),
                    }
                    journal.debit_note_sequence_id = \
                        self.sudo()._create_sequence(
                            journal_vals, type_note='debit').id
        result = super(AccountJournal, self).write(vals)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('type') in ('sale', 'purchasex') \
                and vals.get('debit_note_sequence') \
                    and not vals.get('debit_note_sequence_id'):
                vals.update({
                    'debit_note_sequence_id': self.sudo()._create_sequence(
                        vals, type_note='debit').id
                })
        return super(AccountJournal, self).create(vals_list)

    @api.model
    def _get_sequence_prefix(self, code, refund=False, type_note=False):
        prefix = code.upper()
        if type_note == 'credit' or refund:
            prefix = 'C' + prefix
        if type_note == 'debit':
            prefix = 'D' + prefix
        return prefix  # + '/%(range_year)s/'

    @api.model
    def _create_sequence(self, vals, refund=False, type_note=False):
        ''' Create new no_gap entry sequence for every new Journal'''
        prefix = self._get_sequence_prefix(vals['code'], refund, type_note)
        seq_name = (refund or type_note == 'credit') \
            and prefix + _(': Secuencia Nota Crédito') \
                or type_note == 'debit' \
                    and prefix + _(': Secuencia Nota Débito') \
                        or vals['code']
        seq = {
            'name': '%s' % seq_name,
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
        seq_date_range.number_next = (refund or type_note == 'credit') \
            and vals.get('refund_sequence_number_next', 1) \
                or type_note == 'debit' \
                    and vals.get('debit_note_sequence_number_next', 1) \
                        or vals.get('sequence_number_next', 1)
        return seq

    def create_journal_sequence(self):
        if not self.sequence_id:
            seq = self.create_sequence(refund=False, type_note='')
            self.sequence_id = seq.id
        if self.refund_sequence and not self.refund_sequence_id:
            seq = self.create_sequence(refund=True, type_note='credit')
            self.refund_sequence_id = seq.id
        if self.debit_note_sequence and not self.debit_note_sequence_id:
            seq = self.create_sequence(refund=False, type_note='debit')
            self.debit_note_sequence_id = seq.id

    def create_sequence(self, refund=False, type_note=''):
        prefix = self._get_sequence_prefix(self.code, refund, type_note)
        seq_name = (refund or type_note == 'credit') \
            and self.code + _(': Secuencia Nota Crédito') \
                or type_note == 'debit' \
                    and self.code + _(': Secuencia Nota Débito') \
                        or self.code
        seq = {
            'name': '%s' % seq_name,
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
        seq_date_range.number_next = (refund or type_note == 'credit') \
            and (self.refund_sequence_number_next or 1) \
                or type_note == 'debit' \
                    and (self.debit_note_sequence_number_next or 1) \
                        or (self.sequence_number_next or 1)
        return seq
