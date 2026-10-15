# -*- coding: utf-8 -*-
{
    'name': 'Helpdesk Extend',
    'summary': '''
        Helpdesk module extension.
    ''',
    'description': '''
        - Web form extension with supplemental fields.
        - Guide number servientrega and dates CTB in tickets.
    ''',
    'author': 'OdOne S.A.S.',
    'website': 'https://www.odone.com.co',
    'category': 'Services/Helpdesk',
    'license': 'OPL-1',
    'version': '19.0.0.0.1',
    'depends': [
        'stock',
        'helpdesk',
        'base_address_extended',
        'resource',
        'helpdesk_stock',
        'product_brand',
    ],
    'data': [
        'data/ir_module_category_data.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/damage_type_sm_views.xml',
        'views/res_partner_views.xml',
        'views/helpdesk_team_views.xml',
        'views/helpdesk_ticket_views.xml',
        # 'views/repair_order_views.xml',
        'views/stock_picking_views.xml',
        # 'reports/repair_order_reports.xml',
        # 'reports/repair_order_templates.xml',
        # 'data/denial_letter_mail_template_data.xml',
    ],
}
