# -*- coding: utf-8 -*-
{
    'name': 'Account Move Currency Line Conversion',
    'summary': '''
        Convert invoice line amounts and payment amounts to a new currency,
        using the exchange rate (TRM) configured in Odoo and any conditioned
        rate adjustment defined on the partner
    ''',
    'description': '''
        When the currency of a draft customer invoice or vendor bill is changed,
        this module automatically converts the price of every product line so
        that the economic value of the document is preserved in the new currency.

        It also applies the same conversion logic to customer receipts and vendor
        payments, whether recorded as account.payment records or as the
        account.voucher documents used by this company, so the accounting entry
        generated for a payment uses the same exchange rate (TRM) as the
        documents it settles.

        The conversion uses the exchange rate (TRM) configured in Odoo for the
        source and destination currencies, the company and the document date.

        A partner may also be configured with a conditioned exchange rate
        adjustment (a fixed amount or a percentage added on top of the
        standard rate), which is automatically applied whenever a document or
        payment for that partner is converted. This logic is centralized in a
        single place (res.currency) and reused by invoices and payments alike,
        so both processes always compute the same rate.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.1.0.0',
    'depends': [
        'account',
        'account_voucher',
    ],
    'data': [
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
