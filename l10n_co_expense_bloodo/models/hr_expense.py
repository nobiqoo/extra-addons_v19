# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    ds_journal_id = fields.Many2one(
        'account.journal',
        string='Diario doc. soporte',
        help='Si desea reportar este gasto ante la DIAN, '
        'seleccione un diario de Documento Soporte. '
        'De lo contrario puede dejarlo vacío.'
    )
    
    @api.onchange('journal_id')
    def _onchange_ds_journal_id(self):
        """Auto-populate ds_journal_id if the selected journal has e-invoicing enabled"""
        if self.journal_id and self.journal_id.is_einvoicing:
            self.ds_journal_id = self.journal_id
        else:
            self.ds_journal_id = False

    def _prepare_payments_vals(self):
        """
        Override to include ds_journal_id logic for company-paid expenses.
        If ds_journal_id (Support Document Journal) is set, use it instead of the default journal.
        """
        move_vals, payment_vals = super()._prepare_payments_vals()
        
        # If a support document journal is specified, use it and mark for later sending
        if self.ds_journal_id:
            if not self.ds_journal_id.is_einvoicing:
                raise ValidationError(_(
                    'El diario %s no está activo para Documento Soporte.', 
                    self.ds_journal_id.name))
            move_vals['journal_id'] = self.ds_journal_id.id
            payment_vals['journal_id'] = self.ds_journal_id.id
            # Mark to send later to DIAN (if the field exists in account.move)
            if 'fe_send_later' in self.env['account.move']._fields:
                move_vals['fe_send_later'] = True
        
        return move_vals, payment_vals
