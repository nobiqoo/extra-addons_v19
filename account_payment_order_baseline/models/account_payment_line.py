# -*- coding: utf-8 -*-

from odoo import fields, models, api


class AccountPaymentLine(models.Model):
    _inherit = "account.payment.line"

    exchange_rate = fields.Float(
        compute='compute_exchage_rate',
        string="Exchange rate",
    )

    diff_exchange_rate = fields.Float(
        compute='compute_diff_exchange_rate',
        string="Diff exchange rate",
    )

    def download_report_simple(self):
        return self.env.ref(
            "account_payment_order_baseline.action_print_payment_simple_order"
        ).report_action(self)

    def compute_diff_exchange_rate(self):
        for record in self:
            record.diff_exchange_rate = \
                record.order_id.current_exchange_rate * \
                record.amount_currency - \
                record.exchange_rate*record.amount_currency

    def compute_exchage_rate(self):
        for record in self:
            if record.move_line_id:
                for line in record.move_line_id:
                    if line.move_id:
                        record.exchange_rate = \
                            line.move_id.current_exchange_rate
            else:
                record.exchange_rate = 0

    def _prepare_account_payment_vals(self):
        res = super(AccountPaymentLine, self)._prepare_account_payment_vals()
        res['date'] = self[:1].date
        return res

    @api.model
    def get_bank_account_name(self, partner_bank):
        """

        :param partner_bank:
        :return:
        """
        if partner_bank:
            name = ""
            if partner_bank.bank_name:
                name = "%s: " % partner_bank.bank_id.name
            if partner_bank.acc_number:
                name = f"{name} {partner_bank.acc_number}"
                if partner_bank.bank_bic:
                    name = "%s - " % (name)
            if partner_bank.bank_bic:
                name = f"{name} BIC {partner_bank.bank_bic}"
            return name
        else:
            return False
