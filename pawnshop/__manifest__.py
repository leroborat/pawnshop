# -*- coding: utf-8 -*-
{
    'name': "Pawnshop Management System",
    'summary': "Comprehensive pawnshop management with inventory and invoicing integration",
    'description': """
Complete pawnshop solution for appraisers, cashiers, and administrators.
Includes full ticket lifecycle, renewals, redemptions, forfeitures, auctions,
branch-aware security, and Philippine-ready reports.
    """,
    'author': "iBAS Software, Rein on Odoo",
    'website': "https://www.ibasuite.com/",
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'price': 999.00,
    'currency': 'EUR',
    'support': '1@reinonodoo.com',

    # show your static/description/index.html and images
    'images': [
        'static/description/icon.png',
        'static/description/odooiamgesmall.gif',
        'static/description/odooiamgebig.gif',
    ],

    # Dependencies
    'depends': [
        'base',
        'account',
        'stock',
        'product',
        'contacts',
        'web',
        'mail',
    ],

    # Data files
    'data': [
        'security/pawn_security.xml',
        'security/ir.model.access.csv',

        'data/pawn_sequence.xml',
        'data/pawn_category_data.xml',
        'data/pawn_stock_location.xml',
        'data/pawn_product_data.xml',
        'data/pawn_mail_templates.xml',
        'data/pawn_cron.xml',

        'views/pawn_item_category_views.xml',
        'views/pawn_rate_table_views.xml',
        'views/pawn_ticket_views.xml',
        'views/pawn_inventory_views.xml',
        'views/pawn_intake_wizard_views.xml',
        'views/auction_invoice_wizard_views.xml',
        'views/renew_redeem_wizard_views.xml',
        'views/pawn_branch_views.xml',
        'views/res_config_settings_views.xml',
        'views/pawn_operational_reports_views.xml',
        'views/pawn_dashboard_views.xml',
        'views/pawn_menu.xml',

        'reports/pawn_ticket_report.xml',
        'reports/pawn_renewal_receipt_report.xml',
        'reports/pawn_redemption_receipt_report.xml',
        'reports/pawn_release_form_report.xml',
        'reports/pawn_forfeiture_notice_report.xml',
    ],

    # Demo data
    'demo': [
        'demo/demo.xml',
        'demo/pawn_branch_demo.xml',
        'demo/pawn_rate_table_demo.xml',
        'demo/res_partner_demo.xml',
        'demo/pawn_ticket_demo.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,

    # Front-end assets
    'assets': {
        'web.assets_backend': [
            'web/static/lib/Chart/Chart.js',
            'pawnshop/static/src/css/pawn_dashboard.css',
            'pawnshop/static/src/js/pawn_dashboard.js',
            'pawnshop/static/src/xml/pawn_dashboard.xml',
        ],
    },
}
