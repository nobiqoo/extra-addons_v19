# -*- coding: utf-8 -*-
{
    'name': "Informes de Medios Magnéticos",
    'summary': """
        Reportes de medios magneticos.
    """,
    'description': """
        Reportes de medios magneticos.
    """,
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co/',
    'category': 'Account',
    "version": "19.0.0.1",
    "license": "LGPL-3",
    'depends': [
        'account_accountant',
        'hr_payroll_co'
    ],
    'data': [
        # security
        'security/ir.model.access.csv',
        # 'data/res_country_data.xml',
        # 'data/res.country.csv',
        'data/1001.xml',
        'data/1003.xml',
        'data/1004.xml',
        'data/1005.xml',
        'data/1006.xml',
        'data/1007.xml',
        'data/1008.xml',
        'data/1009.xml',
        'data/1010.xml',
        'data/1011.xml',
        'data/1012.xml',
        'data/2276.xml',
        'data/art_2.xml',
        'data/art_3.xml',
        'data/art_4.xml',
        'data/art_6.xml',
        'data/l10n_latam.identification.type.csv',
        'data/account.account.tag.csv',
        'data/mag.media.lines.csv',
        'data/mag.media.lines.concepts.csv',
        # views
        'views/mag_media_views.xml',
        'views/res_country_views.xml',
        'views/l10n_latam_identification_type_views.xml',
        'views/res_company_views.xml',
    ],
}
