{
    "name": "Approvals Custom",
    "version": "19.0.0.0.1",
    "category": "Custom",
    "summary": "Extensión para agregar Cuentas Analíticas en Productos de Aprobaciones",
    'author': 'OdOne S.A.S',
    'contributors': ['Andres Gil <andresgil@odone.com.co>'],
    'website': 'https://www.odone.com',
    "depends": ["approvals","approval_baseline", "analytic", "purchase", "project_approvals_integration"],
    "data": [
        "views/approval_product_line_views.xml",
    ],
    'license': 'LGPL-3',
    "installable": True,
    "application": False,
}
