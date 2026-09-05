# -*- coding: utf-8 -*-
{
    'name': 'Urban Furniture Accounting System',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Accounting System for Urban Furniture Hackathon',
    'description': """
Urban Furniture: Accounting System
==================================
This module manages budgets, sales, purchases, and accounting integrations 
for Urban Furniture according to the hackathon specifications.
    """,
    'author': 'Antigravity Developer',
    'depends': [
        'base',
        'contacts',
        'sale',
        'purchase',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/uf_budget_views.xml',
        'views/menu_views.xml',
        'data/demo_data.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
