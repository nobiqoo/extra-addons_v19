# -*- coding: utf-8 -*-
{
    'name': 'DIAN Standard Data',
    'summary': '''
        Implements the standard data of the Colombian location
        with the codes used by the DIAN in
        its electronic invoicing processes.
    ''',
    'description': '''
        Implements the standard data of the Colombian location
        with the codes used by the DIAN in
        its electronic invoicing processes. \n\n

        Data that is installed with this module:\n
        - Responsabilidades fiscales definidas por la DIAN (dian.type_code).
        - Tipos de impuesto definidos por la DIAN (dian.tax.type).\n
        - Campos tributarios en el contacto.\n
        - Código DIAN en las ciudades.\n
        - Código DIAN en los departamentos.\n
        - Forzar ciudades al país Colombia.\n
        - Código DIAN en los típos de identificación.\n
        - Código DIAN para las unidades de medida.\n
        - Conceptos de corrección para notas crédito y débito definidos por la DIAN.\n
        - Opciones de pago definidas por la DIAN.\n
        - Códigos de producto y unidad de medida definidos por UNSPSC.\n
    ''',
    'author': 'OdOne S.A.S.',
    'contributors': ['Bernardo David Lara Guevara <bdlgrw@gmail.com, bloodo.dev.solutions@gmail.com>'],
    'website': 'https://www.odone.com.co/',
    'license': 'OPL-1',
    'category': 'Accounting/Localizations',
    'version': '19.0.0.0.1',
    'depends': [
        'base_address_extended',
        'l10n_co',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/l10n_co_data_bloodo_security.xml',
        'data/ir_cron_data.xml',
        'data/account.tax.group.csv',
        'data/dian.type_code.csv',
        'data/dian.tax.type.csv',
        # 'data/account_tax_template_data.xml',
        # 'data/account.tax.template.csv',
        'data/res_partner_data.xml',
        'data/res.city.csv',
        'data/res.country.state.csv',
        'data/res_country_data.xml',
        'data/l10n_latam.identification.type.csv',
        'data/dian.uom.code.csv',
        'data/dian_discrepancy_response_data.xml',
        'data/dian.payment.option.csv',
        'data/dian_event_data.xml',
        'data/dian_claim_concept_data.xml',
        # 'data/product.unspsc.code.csv',  # Se agregan por pyhton
        # 'data/uom_data.xml',
        'views/res_country_state_views.xml',
        'views/res_city_views.xml',
        'views/res_partner_views.xml',
        'views/dian_type_code_views.xml',
        'views/identification_type_views.xml',
        'views/dian_tax_type_views.xml',
        'views/account_tax_views.xml',
        'views/product_uom_views.xml',
        'views/product_template_views.xml',
        'views/dian_discrepancy_response_views.xml',
        'views/dian_payment_option_views.xml',
        'views/dian_uom_code_views.xml',
        'views/product_unspsc_code_views.xml',
        'views/dian_event_views.xml',
        'views/dian_claim_concept_views.xml',
        'views/account_fiscal_position_views.xml',
        'views/res_company_views.xml',
        'views/res_config_views.xml',
        'views/menuitem.xml',
    ],
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
