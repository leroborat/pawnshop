# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    """
    Extend company settings to include pawnshop-specific configuration
    """
    _inherit = 'res.config.settings'

    # Grace Period Settings
    pawn_grace_period_days = fields.Integer(
        string='Grace Period (Days)',
        default=7,
        config_parameter='pawnshop.grace_period_days',
        help="Number of days after maturity date before forfeiture"
    )

    # Interest and Penalties
    pawn_default_maturity_days = fields.Integer(
        string='Default Maturity Period (Days)',
        default=30,
        config_parameter='pawnshop.default_maturity_days',
        help="Default loan maturity period in days"
    )
    pawn_penalty_rate_percent = fields.Float(
        string='Default Penalty Rate (%)',
        default=3.0,
        digits=(5, 2),
        config_parameter='pawnshop.penalty_rate_percent',
        help="Default penalty rate per period for overdue tickets"
    )
    pawn_penalty_period = fields.Selection(
        [
            ('day', 'Per Day'),
            ('month', 'Per Month'),
            ('grace_period', 'Per Grace Period'),
        ],
        string='Penalty Period',
        default='month',
        config_parameter='pawnshop.penalty_period',
        help="Time period for penalty calculation"
    )

    # Service Fees
    pawn_service_fee_percent = fields.Float(
        string='Service Fee (%)',
        default=1.0,
        digits=(5, 2),
        config_parameter='pawnshop.service_fee_percent',
        help="Service fee percentage on loan amount"
    )
    pawn_service_fee_amount = fields.Float(
        string='Fixed Service Fee',
        default=0.0,
        config_parameter='pawnshop.service_fee_amount',
        help="Fixed service fee amount (if any)"
    )
    pawn_service_fee_type = fields.Selection(
        [
            ('percent', 'Percentage'),
            ('fixed', 'Fixed Amount'),
            ('both', 'Both'),
        ],
        string='Service Fee Type',
        default='percent',
        config_parameter='pawnshop.service_fee_type',
        help="How to calculate service fees"
    )

    # Loan-to-Value Settings
    pawn_max_ltv_ratio = fields.Float(
        string='Maximum LTV Ratio (%)',
        default=80.0,
        digits=(5, 2),
        config_parameter='pawnshop.max_ltv_ratio',
        help="Maximum loan-to-value ratio allowed"
    )
    pawn_min_loan_amount = fields.Float(
        string='Minimum Loan Amount',
        default=100.0,
        config_parameter='pawnshop.min_loan_amount',
        help="Minimum loan amount per ticket"
    )
    pawn_max_loan_amount = fields.Float(
        string='Maximum Loan Amount',
        default=500000.0,
        config_parameter='pawnshop.max_loan_amount',
        help="Maximum loan amount per ticket (0 for unlimited)"
    )

    # KYC Settings
    pawn_require_kyc = fields.Boolean(
        string='Require KYC',
        default=True,
        config_parameter='pawnshop.require_kyc',
        help="Require KYC documentation for all transactions"
    )
    pawn_require_photo = fields.Boolean(
        string='Require Item Photos',
        default=True,
        config_parameter='pawnshop.require_photo',
        help="Require photos for all pawned items"
    )
    pawn_min_customer_age = fields.Integer(
        string='Minimum Customer Age',
        default=18,
        config_parameter='pawnshop.min_customer_age',
        help="Minimum age requirement for customers"
    )

    # Notification Settings
    pawn_enable_notifications = fields.Boolean(
        string='Enable Notifications',
        default=True,
        config_parameter='pawnshop.enable_notifications',
        help="Send SMS/email notifications to customers"
    )
    pawn_notify_days_before_maturity = fields.Integer(
        string='Notify Before Maturity (Days)',
        default=3,
        config_parameter='pawnshop.notify_days_before_maturity',
        help="Send reminder notification X days before maturity"
    )
    pawn_notify_grace_period = fields.Boolean(
        string='Notify Grace Period',
        default=True,
        config_parameter='pawnshop.notify_grace_period',
        help="Send notification when ticket enters grace period"
    )

    # Auction Settings
    pawn_auto_auction_after_days = fields.Integer(
        string='Auto-Auction After (Days)',
        default=30,
        config_parameter='pawnshop.auto_auction_after_days',
        help="Days after forfeiture to automatically create auction lot (0 to disable)"
    )
    pawn_auction_starting_percent = fields.Float(
        string='Auction Starting Bid (%)',
        default=50.0,
        digits=(5, 2),
        config_parameter='pawnshop.auction_starting_percent',
        help="Starting bid as percentage of appraised value"
    )
    pawn_auction_customer_id = fields.Many2one(
        'res.partner',
        string='Default Auction Customer',
        config_parameter='pawnshop.auction_customer_id',
        help="Default customer to use for auction sale invoices (can be a placeholder such as 'Auction Buyer')."
    )

    # Product Configuration (for invoicing)
    pawn_interest_product_id = fields.Many2one(
        'product.product',
        string='Interest Income Product',
        config_parameter='pawnshop.interest_product_id',
        domain=[('type', '=', 'service')],
        help="Product used for interest income in invoices"
    )
    pawn_penalty_product_id = fields.Many2one(
        'product.product',
        string='Penalty Product',
        config_parameter='pawnshop.penalty_product_id',
        domain=[('type', '=', 'service')],
        help="Product used for penalty fees in invoices"
    )
    pawn_service_fee_product_id = fields.Many2one(
        'product.product',
        string='Service Fee Product',
        config_parameter='pawnshop.service_fee_product_id',
        domain=[('type', '=', 'service')],
        help="Product used for service fees in invoices"
    )

    # Print Settings
    pawn_print_qr_code = fields.Boolean(
        string='Print QR Code on Tickets',
        default=True,
        config_parameter='pawnshop.print_qr_code',
        help="Include QR code on printed pawn tickets"
    )
    pawn_print_terms = fields.Boolean(
        string='Print Terms and Conditions',
        default=True,
        config_parameter='pawnshop.print_terms',
        help="Include terms and conditions on pawn tickets"
    )
    pawn_terms_text = fields.Char(
        string='Terms and Conditions',
        config_parameter='pawnshop.terms_text',
        help="Terms and conditions text to print on tickets (or create a separate template)"
    )

    # Default Rate Table
    pawn_default_rate_table_id = fields.Many2one(
        'pawn.rate.table',
        string='Default Rate Table',
        config_parameter='pawnshop.default_rate_table_id',
        help="Default rate table for new tickets"
    )

    @api.model
    def get_values(self):
        """Get configuration values"""
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()

        # Convert Many2one fields from ID strings
        interest_product = params.get_param('pawnshop.interest_product_id')
        penalty_product = params.get_param('pawnshop.penalty_product_id')
        service_fee_product = params.get_param('pawnshop.service_fee_product_id')
        default_rate_table = params.get_param('pawnshop.default_rate_table_id')

        res.update(
            pawn_interest_product_id=int(interest_product) if interest_product else False,
            pawn_penalty_product_id=int(penalty_product) if penalty_product else False,
            pawn_service_fee_product_id=int(service_fee_product) if service_fee_product else False,
            pawn_default_rate_table_id=int(default_rate_table) if default_rate_table else False,
        )
        return res

    def set_values(self):
        """Set configuration values"""
        super(ResConfigSettings, self).set_values()
        params = self.env['ir.config_parameter'].sudo()

        # Store Many2one fields as ID strings
        params.set_param('pawnshop.interest_product_id', self.pawn_interest_product_id.id or False)
        params.set_param('pawnshop.penalty_product_id', self.pawn_penalty_product_id.id or False)
        params.set_param('pawnshop.service_fee_product_id', self.pawn_service_fee_product_id.id or False)
        params.set_param('pawnshop.default_rate_table_id', self.pawn_default_rate_table_id.id or False)
        params.set_param('pawnshop.auction_customer_id', self.pawn_auction_customer_id.id or False)
