# -*- coding: utf-8 -*-
{
    'name': "Accounting and Financing",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Online accounting system for small scale businesses.
    """,

    'author': "TechWorx LLC.",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/10.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','report','oasys_product','oasys_analytics'],

    # always loaded
    'data': [
        'security/account_security.xml',
        'security/ir.model.access.csv',
        #'data/data.xml',
        'views/chart_of_accounts.xml',
        'views/product_view.xml',
        'views/journal_view.xml',
        'views/config_views.xml',
        #'views/income_statement.xml',
        #'views/balance_sheet.xml',
        #'views/company_view.xml',
        'views/account_receipt.xml',
        'views/account_invoice.xml',
        'views/account_view.xml',
        'views/visualisation.xml',
        'views/views.xml',
        # 'views/accounts_accounts.xmls',
        # 'views/templates.xml',
        #'reports/income_statement.xml',
        'reports/paper_sizes.xml',
        'reports/invoice_report_template.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}