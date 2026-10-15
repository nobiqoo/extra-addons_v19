# -*- coding: utf-8 -*-
from base64 import b64encode, b64decode
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPaymentOrder(models.Model):
    _inherit = 'account.payment.order'

    txt_filename = fields.Char(string="Name txt file")
    txt_file = fields.Binary(string="Txt file")

    def generate_txt(self):
        txt_setting_obg = self.env['res.bank.txt_config']
        for record in self:
            bank_id = record.journal_id.bank_id or False
            if not bank_id:
                raise ValidationError(_('Bank not found'))
            txt_setting_id = txt_setting_obg.search(
                [('bank_id', '=', bank_id.id), ('state', '=', 'active')])
            if not txt_setting_id:
                raise ValidationError(_(
                    'No txt configuration record found for bank %s'
                ) % bank_id.name)
            elif len(txt_setting_id) > 1:
                return {
                    'name': _('Bank txt generation'),
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'res.bank.txt.select.wizard',
                    # 'views': [(compose_form.id, 'form')],
                    # 'view_id': compose_form.id,
                    'target': 'new',
                    'context': {
                        'default_order_id': record.id,
                        'default_bank_id': bank_id.id,
                        'default_msg': _(
                            'There are %s bank txt formats for %s bank. '
                            'Please, select the format that you want'
                            ' to generate.'
                        ) % (len(txt_setting_id), bank_id.name)
                    },
                }
            else:
                record._generate_txt(txt_setting_id)

    def _generate_txt(self, txt_setting_id=False):
        self.ensure_one()
        if not txt_setting_id:
            raise ValidationError(_(
                'No bank txt configuration record selected.'
            ))
        txt = txt_setting_id.get_txt(self)
        date_txt = fields.Datetime.context_timestamp(self, datetime.now())
        self.txt_filename = 'PAGO_' + self.name + '_' + txt_setting_id.name + \
            '_' + date_txt.strftime('%d-%m-%Y %H:%M:%S') + '.txt'
        self.txt_file = b64encode(
            txt.encode('utf-8')
        ).decode('utf-8', 'ignore')

    def get_variables_availables(self):
        self.ensure_one()
        company = self.journal_id.company_id
        return {
            'z_company_name': company.name,
            'z_company_nit': company.partner_id.vat,
            # 'z_company_nit_dv': company.partner_id.l10n_co_verification_code,
            # 'z_payment_date': self.order_date,
            'z_date_now': fields.Datetime.context_timestamp(self,
                                                            datetime.now()),
            'z_total_amount': sum(
                self.payment_line_ids.mapped('amount_currency')),
            'z_total_cc_amount': sum(
                self.payment_line_ids.mapped('amount_company_currency')),
            'z_n_lines': len(set(self.payment_line_ids.mapped('partner_id'))),
            'z_debit_bank_account': self.company_partner_bank_id.acc_number,
        }


class AccountPaymentLine(models.Model):
    _inherit = 'account.payment.line'

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
