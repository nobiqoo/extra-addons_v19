# -*- coding: utf-8 -*-
{
    'name': 'Stock Reports',
    'summary': '''
        View and create reports
    ''',
    'description': '''
        - falta descripcion.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'contributors': [
        'Juan Arcos juanparmer@gmail.com'
    ],
    'category': 'Inventory/Inventory',
    'license': 'LGPL-3',
    'version': '19.0.0.0.1',
    'depends': [
        'date_range',
        'report_xlsx',
        'stock_account'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_move_template.xml',
        'views/stock_picking_template.xml',
        'report/stock_move_report.xml',
        'report/stock_valuation_report.xml',
        'report/stock_picking_report.xml',
        'wizard/stock_move_wizard.xml',
        'wizard/stock_valuation_wizard.xml',
    ],
}
