# -*- coding: utf-8 -*-

{
    'name': 'Journal sequence in accounting moves.',
    'summary': '''
        Journal sequence in accounting moves.
    ''',
    'description': '''
        Journal sequence in accounting moves.
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': ['Bernardo David Lara Guevara <bdlgrw@gmail.com, bloodo.dev.solutions@gmail.com>'],
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Accounting',
    'version': '19.0.0.0.1',
    'depends': ['account'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/account_journal.xml',
    ],
    'installable': True,
    'images': ['static/description/banner.png'],
}
