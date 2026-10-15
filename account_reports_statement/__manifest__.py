# -*- coding: utf-8 -*-
{
    'name': 'Estados de Cuentas',
    'summary': 'Cartera por edades de cuentas por cobrar y por pagar con datos de la operación',
    'description': '''
        Migración a Odoo 19 del informe "Estados de cuentas" de Consolcargo
        (account.accounts.states de account_reports_consolcargo v15).

        Cartera por edades que reúne cuentas por cobrar y por pagar en un solo
        informe, con columnas adicionales por documento: factura, moneda,
        analítica, identificación del tercero, contenedor, referencia, origen,
        destino, país, diario, TRM, posición, total factura y total adeudado.

        Los campos de la operación logística (contenedor, posición, origen,
        destino, TRM) se muestran solo si algún módulo instalado los define en
        account.move (account_cargowise_sync, account_logistic_odone, ...).
    ''',
    'author': 'OdOne S.A.S',
    'website': 'https://www.odone.com.co/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.1.0.0',
    'depends': [
        'account_reports',
    ],
    'data': [
        'data/account_statement_report.xml',
    ],
    'installable': True,
}
