# -*- coding: utf-8 -*-
{
    'name': "l10n_co_dian_invoice_ai",

    'summary': "AI agent that posts vendor bills from synchronized DIAN documents",

    'description': """
DIAN vendor bill agent - Colombia
=================================

Takes the DIAN documents with the XML loaded whose purchase order is approved, creates
the vendor bill from the purchase order, crosses it against the XML, reviews its taxes
and posts it when everything matches. Anything that does not match stays as a draft or
in the exceptions view for the accountant, whose corrections become rules for the agent.

Amounts are always computed by Odoo. The checks that allow posting, and the RADIAN
events, are plain code: the model cannot skip the former nor send the latter.
    """,

    'author': "OdOne S.A.S",
    'website': "https://www.odone.com.co/",

    'category': 'Accounting/Localizations',
    'version': '19.0.1.0.0',
    'countries': ['co'],

    'depends': [
        'l10n_co_bloodo',
        'purchase',
        'account_tax',
        'ai_app',
        'ai_anthropic',
    ],

    'data': [
        'security/dian_ai_security.xml',
        'security/ir.model.access.csv',

        'data/ai_agent_data.xml',
        'data/ir_cron_data.xml',

        'views/dian_ai_config_views.xml',
        'views/dian_ai_rule_views.xml',
        'views/dian_ai_run_views.xml',
        'views/dian_document_views.xml',
        'views/account_move_views.xml',
        'wizards/dian_ai_explain_wizard_views.xml',
        'views/dian_ai_menus.xml',
    ],

    'license': 'LGPL-3',
}
