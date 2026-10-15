# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    account_advance_id = fields.Many2one(
        'account.voucher',
        string="Cuenta anticipo"
    )
    check_immediate_payment = fields.Boolean()
    account_voucher_ids = fields.Many2many(
        comodel_name='account.voucher',
        string='Account Voucher Advance'
    )
    active_payment_advance = fields.Boolean(
        'Enable payment with advances'
    )
    advance_payment_manually = fields.Boolean(
        'Autorizar sin anticipo',
        help='Autorizar si el pedido está bloqueado por no tener anticipos.',
    )
    group_advance_validate_manually = fields.Boolean(
        compute="_compute_group_account_advance_validate_manually"
    )

    def _compute_group_account_advance_validate_manually(self):
        for record in self:
            record.group_advance_validate_manually = self.env.user.has_group(
                'account_voucher.group_account_advance_validate_manually')

    @api.onchange('account_voucher_ids')
    def check_account_voucher_ids(self):
        for record in self:
            if record.account_voucher_ids:
                ids_voucher = record.account_voucher_ids.ids
                sales = self.env['sale.order'].search([])
                ids_advances = [x.id for x in sales.account_voucher_ids]
                for id_voucher in ids_voucher:
                    for id_advance in ids_advances:
                        if id_advance == id_voucher:
                            raise ValidationError(
                                _('This Advance is already related in another order'))

    @api.onchange('advance_payment_manually')
    def clean_account_voucher_ids(self):
        for record in self:
            if record.advance_payment_manually:
                record.account_voucher_ids = False

    @api.onchange('payment_term_id')
    def compute_immediate_payment(self):
        for record in self:
            if record.payment_term_id.immediate_payment is True:
                record.check_immediate_payment = True
            else:
                record.check_immediate_payment = False
                record.account_voucher_ids = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['account_voucher_ids'] = False
            vals['advance_payment_manually'] = False
        return super(SaleOrder, self).create(vals_list)
