{
    'name': "Difference in change caused",
    'summary': '''
       Diferencia en cambio causada
    ''',
    'description': '''
        - falta descripcion.
    ''',
    'version': '19.0.0.0.1',
    'depends': ['account_ifrs', 'account_baseline'],
    'author': "Odone SAS",
    'category': 'Accounting',
    'description': """
        In this module can create difference in change of invoices in external currency.
    """,
    'data': [
        'data/res_groups.xml',
        'data/model_sequence.xml',
        'security/ir.model.access.csv',
        'views/difference_in_change_maker_views.xml'

    ],
    'license': 'LGPL-3',
}