# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountVoucher(models.Model):
    _inherit = "account.voucher"

    payment_method_line_id = fields.Many2one(
        comodel_name='account.payment.method.line',
        string='Payment Method',
        compute='_compute_payment_method_line_id',
        store=True,
        readonly=False,
        copy=False,
        domain="[('id', 'in', available_payment_method_line_ids)]",
    )
    available_payment_method_line_ids = fields.Many2many(
        comodel_name='account.payment.method.line',
        compute='_compute_available_payment_method_line_ids',
    )
    show_payment_method_line_id = fields.Boolean(
        compute='_compute_show_payment_method_line_id',
    )
    check_number = fields.Char(
        string='N° de Cheque',
        compute='_compute_check_number',
        inverse='_inverse_check_number',
        store=True,
        readonly=False,
        copy=False,
    )
    show_check_number = fields.Boolean(
        compute='_compute_show_check_number',
    )

    @api.depends('journal_id', 'partner_type')
    def _compute_available_payment_method_line_ids(self):
        for voucher in self:
            if voucher.partner_type == 'supplier' and voucher.journal_id:
                voucher.available_payment_method_line_ids = voucher.journal_id._get_available_payment_method_lines('outbound')
            else:
                voucher.available_payment_method_line_ids = False

    @api.depends('available_payment_method_line_ids')
    def _compute_show_payment_method_line_id(self):
        for voucher in self:
            voucher.show_payment_method_line_id = len(voucher.available_payment_method_line_ids) > 1

    @api.depends('journal_id', 'partner_type')
    def _compute_payment_method_line_id(self):
        for voucher in self:
            available_payment_method_lines = voucher.available_payment_method_line_ids
            if voucher.payment_method_line_id in available_payment_method_lines:
                voucher.payment_method_line_id = voucher.payment_method_line_id
            elif available_payment_method_lines:
                voucher.payment_method_line_id = available_payment_method_lines[0]._origin
            else:
                voucher.payment_method_line_id = False

    @api.depends('journal_id', 'payment_method_line_id')
    def _compute_check_number(self):
        for voucher in self:
            if voucher.payment_method_line_id.code == 'check_printing' and voucher.journal_id.check_manual_sequencing:
                sequence = voucher.journal_id.check_sequence_id
                voucher.check_number = sequence.get_next_char(sequence.number_next_actual)
            else:
                voucher.check_number = voucher.check_number

    def _inverse_check_number(self):
        for voucher in self:
            if voucher.check_number and voucher.journal_id.check_manual_sequencing:
                voucher.journal_id.check_sequence_id.sudo().padding = len(voucher.check_number)

    @api.depends('payment_method_line_id', 'check_number')
    def _compute_show_check_number(self):
        for voucher in self:
            voucher.show_check_number = (
                voucher.payment_method_line_id.code == 'check_printing'
                and bool(voucher.check_number)
            )

    def action_post(self):
        for voucher in self.filtered(
            lambda v: v.payment_method_line_id.code == 'check_printing' and v.journal_id.check_manual_sequencing
        ):
            sequence = voucher.journal_id.check_sequence_id
            voucher.check_number = sequence.next_by_id()
        return super().action_post()
