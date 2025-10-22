{
    'name': "Pawnshop Management System",
    'summary': "Comprehensive pawnshop management with inventory and invoicing integration",
    'description': """
Pawnshop Management System
==========================
Complete solution for pawnshop operations including:
* Multi-branch support with security
* Pawn ticket management with automated workflows
* Inventory tracking for collateral and forfeited items
* Invoicing integration for renewals, redemptions, and sales
* Rate tables and interest calculations
* KYC management and reporting
* Notifications and automated reminders
    """,
    'author': "Custom Development",
    'website': "https://www.yourcompany.com",
    'category': 'Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',

    # Module dependencies
    'depends': [
        'base',
        'account',      # Invoicing (Community)
        'stock',        # Inventory Management
        'product',      # Product Management
        'contacts',     # Customer Management
        'web',          # Web Interface
        'mail',         # Notifications
    ],

    # Data files loaded in order
    'data': [
        # Security
        'security/pawn_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/pawn_sequence.xml',
        'data/pawn_category_data.xml',
        'data/pawn_stock_location.xml',
        'data/pawn_product_data.xml',

        # Views
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
        'views/pawn_menu.xml',

        # Reports (PDF)
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
}

