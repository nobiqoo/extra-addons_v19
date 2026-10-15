# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api
import logging
import base64
_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_fee_element = fields.Boolean(string='Is Fee Element?', default=False)

    libray_element = fields.Boolean(string='Is Library Element?', default=False)


class FeeComponent(models.Model):

    _name = "fee.component"
    _description = "Fee Component"
    _order = "sequence desc"

    sequence = fields.Integer(required=True, default=10)
    product_id = fields.Many2one('product.product', string="Fee Element",
                                 required=True, domain="[('is_fee_element','=',True)]")
    fee = fields.Float(string="Fee", required=True)
    frequency = fields.Selection(
        [('one', 'Once'), ('multi', 'Recurring')], string="Frequency", required=True)
    structure_id = fields.Many2one('fee.structure', string="Fee Structure")

    @api.onchange('product_id')
    def _onchange_product_id_set_fee(self):
        if self.product_id:
            self.fee = self.product_id.lst_price


class FeeStructure(models.Model):

    _name = "fee.structure"
    _inherit = "wk.company.visibility.mixin"
    _description = "Fee Structure"

    name = fields.Char(string="Title", required=True)
    company_id = fields.Many2one(
        'res.company', string="School", required=True, default=lambda self: self.env.company)
    grade_id = fields.Many2one('wk.school.grade', string="Class",
                               required=True, domain="[('company_id','=',company_id)]")
    fee_component_ids = fields.One2many(
        "fee.component", 'structure_id', string="Fee Components")
    late_fee_enable = fields.Boolean(string='Enable late fee?')
    late_fee_amount = fields.Float(string='Late fee charges')
    description = fields.Html(string='Terms and Conditions')
    currency_id = fields.Many2one('res.currency', string="Currency", required=True)


class AccountMove(models.Model):
    _inherit = "account.move"

    fee_slip_id = fields.Many2one('wk.fee.slip', string='Fee Slip', copy=False, readonly=True, ondelete='cascade')

    def get_fee_slip_id(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wk.fee.slip',
            'view_mode': 'form',
            'res_id': self.fee_slip_id.id,
            'views': [[self.env.ref('wk_school_management.wk_fee_slip_view_form').id, 'form']],
        }


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _reconcile_post_hook(self, data):
        super()._reconcile_post_hook(data)
        # Sincroniza los fee slips ligados a las facturas involucradas en
        # cualquier conciliación (wizard de pago, extracto bancario,
        # conciliación manual, notas de crédito, etc.)
        self.move_id.fee_slip_id._sync_payment_state()


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def action_create_payments(self):
        res = super().action_create_payments()
        for line in self.line_ids:
            invoice = line.move_id
            if not invoice:
                continue
            fee_slip = invoice.fee_slip_id
            payment_tx = self.env['payment.transaction'].search([('invoice_ids', 'in', invoice.ids)], limit=1)
            if not payment_tx:
                payment_tx = self.env['payment.transaction'].search([('reference', '=', invoice.name)], limit=1)

            if payment_tx.exists() and fee_slip:
                payment_tx.fee_slip_ids = [(4, fee_slip.id)]

            if fee_slip:
                fee_slip._sync_payment_state()

                if invoice.state == 'posted':
                    mail_template = self.env.ref('wk_school_management.fee_slip_success_mail', raise_if_not_found=False)
                    if mail_template:
                        report_action = self.env['ir.actions.report']\
                            .with_context(force_report_rendering=True)\
                            ._render('account.account_invoices', invoice.id)
                        attachment = self.env['ir.attachment'].create({
                            'name': f'Invoice_{invoice.name}.pdf',
                            'type': 'binary',
                            'datas': base64.b64encode(report_action[0]),
                            'res_model': 'wk.fee.slip',
                            'res_id': fee_slip.id,
                            'mimetype': 'application/pdf',
                        })
                        mail_template.attachment_ids = attachment
                        mail_template.send_mail(fee_slip.id)
        return res

