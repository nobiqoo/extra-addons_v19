# -*- coding: utf-8 -*-
{
    "name": "Purchase Approval Sale (Delegación y Autoridad Cotizaciones)",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "summary": "Matriz de Delegación y Autoridad para enviar cotizaciones (SMMLV, aprobaciones secuenciales)",
    "author": "Linalca",
    "license": "LGPL-3",
    "depends": ["sale", "sales_team", "mail"],
    "data": [
        'security/ir.model.access.csv',
        'security/security.xml',
        "views/delegation_matrix_views.xml",
        "views/sale_order_views.xml",
    ],
    "application": False,
    "installable": True,
}
