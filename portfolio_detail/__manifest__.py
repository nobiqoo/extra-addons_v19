{
	'name': "Portfolio Detail",
	'version': '19.0.1.0.0',
	'depends': ['account_reports'],
	'author': "Odone SAS",
    'license': 'LGPL-3',
	'category': 'Sales',
	'description': """
		This module generate a report of invoices
		show the payment method
	""",
	# data files always loaded at installation
	'data': [
        'reports/portfolio_detail_report_action.xml',
        'reports/portfolio_detail_report_template.xml',
        'reports/portfolio_detail_xlsx_template.xml',
		'views/portfolio_detail_wizard_views.xml',
        'security/ir.model.access.csv',
	],
}