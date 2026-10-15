# -*- coding: utf-8 -*-
{
    'name': 'Account Payment Order Baseline',
    'summary': '''
        Ordenes de pago Baseline.
    ''',
    'description': '''
        - Tasa de cambio modificable en ordenes de pago.
        - Quitar validación de tamaño del numero de cuenta bancaria (bic).
        - Cuenta de cobro desde el diario.
        - Cuenta de pago desde el diario.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Banking addons',
    'version': '19.0.0.0.3',
    'depends': [
        'account_payment_order',
        'account_baseline',
        'account_voucher',
    ],
    'data': [
        'security/account_payment_order_baseline_groups.xml',
        'security/ir.model.access.csv',
        'wizard/account_payment_order_remove_partners_wizard_views.xml',
        'views/account_payment_mode.xml',
        'views/account_payment_order_views.xml',
        'views/res_company_views.xml',
        'report/account_payment_order.xml',
        'report/print_account_payment_order.xml',
        'report/account_payment_order_supplier_group.xml',
        'report/print_account_payment_order_supplier_group.xml',
    ],
}
