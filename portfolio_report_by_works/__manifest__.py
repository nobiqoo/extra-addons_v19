{
    'name': "Porfolio report by works",
    'version': '19.0.1.0.0',
    'depends': ['account','sale_order_work'],
    'author': "Odone SAS",
    'license': 'LGPL-3',
    'category': 'Accounting',
    'description': """
        In this module is generated a xlsx report for download 
        porfolio report of sales by work.
    """,
    # data files always loaded at installation
    'data': [
        'security/ir.model.access.csv',
        'views/portfolio_works_report_views.xml'
    ],
}