# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountPaymentLineTemp(models.TransientModel):
    _name = 'account.payment.line.temp'
    _description = 'Payment lines temporal grouped by partner'

    name = fields.Char("Payment Reference",
                       readonly=True,
                       copy=False)
    order_id = fields.Many2one("account.payment.order",
                               "Payment Order",
                               ondelete="cascade",
                               index=True,
                               check_company=True)
    # move_line_id = fields.Many2one("account.move.line",
    #                         "Journal Item",
    #                         ondelete="restrict",
    #                         check_company=True)
    # currency_id = fields.Many2one("res.currency",
    #                         "Currency of the Payment Transaction",
    #                         required=True,
    #                         default=lambda self: self.env.user.company_id.currency_id)
    amount_currency = fields.Float("Amount")
    amount_company_currency = fields.Float("Amount in Company Currency")
    partner_id = fields.Many2one("res.partner",
                                 "Partner",
                                 required=True,
                                 domain=[("parent_id", "=", False)],
                                 check_company=True)
    partner_bank_id = fields.Many2one("res.partner.bank",
                                      "Partner Bank Account",
                                      required=False,
                                      ondelete="restrict",
                                      check_company=True)
    date = fields.Date("Payment Date")
    communication = fields.Char(required=False,
                                help="Label of the payment that will be seen by the destinee")

    def get_variables_availables(self):
        self.ensure_one()
        partner = self.partner_id
        bank_partner = self.partner_bank_id.bank_id
        acc_bank_partner = self.partner_bank_id

        return {
            'z_benef_nit': partner.vat,
            # 'z_benef_nitdv': partner.l10n_co_verification_code,
            'z_benef_name': partner.name,
            'z_benef_bank_account': acc_bank_partner.acc_number,
            'z_benef_bank_account_bic': bank_partner.bic,
            'z_amount': self.amount_currency,
            'z_cc_amount': self.amount_company_currency,
            'z_communication': self.communication,
            'z_communication2': '',
            'z_ref': self.name,
            'z_seq': 0,
        }
