# -*- coding: utf-8 -*-
{
    'name': "AI Anthropic Provider",

    'summary': "Use Claude (Anthropic) as an LLM provider of the Odoo AI app",

    'description': """
Anthropic provider for the AI app
=================================

Adds the Claude models to the agents of the standard ``ai`` module, using the
official Anthropic Python SDK. The API key is set in the General Settings
(or the ODOO_AI_ANTHROPIC_TOKEN environment variable).

Anthropic has no embeddings API, so an agent running on Claude cannot use the
agent sources (RAG) of the standard module.
    """,

    'author': "OdOne S.A.S",
    'website': "https://www.odone.com.co/",

    'category': 'Productivity',
    'version': '19.0.1.0.0',

    'depends': [
        'ai',
    ],

    'external_dependencies': {
        'python': ['anthropic'],
    },

    'data': [
        'views/res_config_settings_views.xml',
    ],

    'license': 'LGPL-3',
}
