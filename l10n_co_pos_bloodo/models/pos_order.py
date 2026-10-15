# -*- coding: utf-8 -*-

import markupsafe
from odoo import api, fields, models, _

class PosOrder(models.Model):
    _inherit = 'pos.order'

    to_einvoice = fields.Boolean('To e-invoice', default=False, copy=False)

    @api.model
    def _process_order(self, order, existing_order):
        order['to_einvoice'] = order.get('to_einvoice', False)
        order['to_invoice'] = order.get('to_invoice', False) \
            or order.get('to_einvoice', False) or False
        vals = super(PosOrder, self)._process_order(order, existing_order)
        return vals

    def _prepare_invoice_vals(self):
        vals = super(PosOrder, self)._prepare_invoice_vals()
        if self.to_einvoice and self.to_invoice:
            default_payment_option_id = self.env['dian.payment.option'].search([('dian_code', '=', '1')], limit=1)
            vals['journal_id'] = self.session_id.config_id.einvoice_journal_id.id
            self_payment_op_ids = [x.fe_payment_option_id or False for x in self.payment_ids.mapped('payment_method_id')]
            while False in self_payment_op_ids:
                self_payment_op_ids.remove(False)
            vals['fe_payment_option_id'] = self_payment_op_ids and self_payment_op_ids[0].id or default_payment_option_id.id
            if vals.get('move_type', False) == 'out_refund':
                if self.refunded_order_id and self.amount_total + self.refunded_order_id.amount_total == 0:
                    vals['fe_correction_id'] = self.env.ref('l10n_co_data_bloodo.discrepancy_response_credit_02').id
                else:
                    vals['fe_correction_id'] = self.env.ref('l10n_co_data_bloodo.discrepancy_response_credit_01').id
        if vals.get('move_type', False) == 'out_refund':
            vals['type_note'] = 'credit'
        return vals

    def get_invoice(self):
        self.ensure_one()
        out = {}
        invoice = self.account_move or False
        if invoice:
            if invoice.journal_id.is_einvoicing:
                act_resolution = invoice._aktive_auflosung_erhalten()
                out = {
                    'number': invoice.name,
                    'einvoice': True,
                    'fe_uuid': invoice.fe_cufe_cude_ref,
                    'fe_url': invoice.fe_url,
                    'fe_qr_data': '',
                    'fe_state': invoice.fe_state,
                    'fe_response': invoice.fe_response,
                    'resolution_text': invoice.journal_id.resolution_text,
                    'fe_notes': invoice.journal_id.note_ei or '',
                    'resolution_number': act_resolution.get('resolution_number'),
                    # 'resolution_resolution_date': invoice.resolution_id.resolution_resolution_date,
                    'resolution_prefix': act_resolution.get('prefix'),
                    'resolution_from': act_resolution.get('number_from'),
                    'resolution_to': act_resolution.get('number_to'),
                    'resolution_date_from': act_resolution.get('date_from'),
                    'resolution_date_to': act_resolution.get('date_to'),
                }
            else:
                out = {
                    'number': invoice.name,
                    'einvoice': False,
                }
        return out
    
    def action_pos_order_einvoice(self):
        self.write({'to_einvoice': True})
        return self.action_pos_order_invoice()
