# -*- coding: utf-8 -*-
{
    'name': 'Representación Gráfica Geoflora',
    'summary': 'Detalle agrupado por categoría y valor unitario, e información WebFlor en la RG de facturación electrónica',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Accounting/Accounting',
    'version': '19.0.0.0.1',
    'depends': [
        'l10n_co_bloodo',
        'webflor_sale_integration',
    ],
    'data': [
        'views/res_company_views.xml',
        'views/account_journal_views.xml',
        'views/product_category_views.xml',
        'reports/einvoicing_document.xml',
    ],
    'installable': True,
    'application': False,
}
