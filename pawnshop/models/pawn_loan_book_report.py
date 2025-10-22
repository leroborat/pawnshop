# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta


class PawnLoanBookReport(models.Model):
    """Loan Book & Aging Report - Shows all active loans with aging buckets"""
    _name = 'pawn.loan.book.report'
    _description = 'Loan Book & Aging Report'
    _auto = False
    _order = 'date_maturity asc, ticket_no'

    # Ticket Information
    ticket_id = fields.Many2one('pawn.ticket', string='Ticket', readonly=True)
    ticket_no = fields.Char(string='Ticket No', readonly=True)
    branch_id = fields.Many2one('pawn.branch', string='Branch', readonly=True)
    customer_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    
    # Dates
    date_created = fields.Datetime(string='Date Created', readonly=True)
    date_pledged = fields.Date(string='Date Pledged', readonly=True)
    date_maturity = fields.Date(string='Maturity Date', readonly=True)
    
    # Financial
    principal_amount = fields.Monetary(string='Principal', readonly=True, currency_field='currency_id')
    interest_amount = fields.Monetary(string='Interest', readonly=True, currency_field='currency_id')
    total_due = fields.Monetary(string='Total Due', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    # Aging Analysis
    days_to_maturity = fields.Integer(string='Days to Maturity', readonly=True)
    days_overdue = fields.Integer(string='Days Overdue', readonly=True)
    aging_bucket = fields.Selection([
        ('current', 'Current'),
        ('due_soon', 'Due Soon (< 7 days)'),
        ('matured', 'Matured'),
        ('grace', 'In Grace Period'),
        ('overdue', 'Overdue'),
    ], string='Aging Bucket', readonly=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('renewed', 'Renewed'),
        ('redeemed', 'Redeemed'),
        ('forfeited', 'Forfeited'),
        ('cancelled', 'Cancelled'),
    ], string='Status', readonly=True)
    
    item_count = fields.Integer(string='Item Count', readonly=True)

    def init(self):
        """Create the view for the loan book report"""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pawn_loan_book_report AS (
                SELECT 
                    pt.id as id,
                    pt.id as ticket_id,
                    pt.ticket_no,
                    pt.branch_id,
                    pt.customer_id,
                    pt.date_created,
                    pt.date_pledged,
                    pt.date_maturity,
                    pt.principal_amount,
                    pt.interest_amount,
                    pt.total_due,
                    pt.company_id,
                    c.currency_id,
                    pt.state,
                    (SELECT COUNT(*) FROM pawn_ticket_line WHERE ticket_id = pt.id) as item_count,
                    
                    -- Days to maturity (negative if overdue)
                    CASE 
                        WHEN pt.date_maturity >= CURRENT_DATE 
                        THEN (pt.date_maturity - CURRENT_DATE)
                        ELSE 0
                    END as days_to_maturity,
                    
                    -- Days overdue (0 if not overdue)
                    CASE 
                        WHEN pt.date_maturity < CURRENT_DATE 
                        THEN (CURRENT_DATE - pt.date_maturity)
                        ELSE 0
                    END as days_overdue,
                    
                    -- Aging bucket classification
                    CASE
                        WHEN pt.date_maturity > CURRENT_DATE + INTERVAL '7 days' THEN 'current'
                        WHEN pt.date_maturity > CURRENT_DATE THEN 'due_soon'
                        WHEN pt.date_maturity = CURRENT_DATE THEN 'matured'
                        WHEN (CURRENT_DATE - pt.date_maturity) <= (
                            SELECT CAST(value AS INTEGER) 
                            FROM ir_config_parameter 
                            WHERE key = 'pawnshop.grace_period_days'
                            LIMIT 1
                        ) THEN 'grace'
                        ELSE 'overdue'
                    END as aging_bucket
                    
                FROM pawn_ticket pt
                LEFT JOIN res_company c ON c.id = pt.company_id
                WHERE pt.state IN ('active', 'renewed')
            )
        """)

    @api.model
    def get_aging_summary(self, branch_id=None):
        """Get summary statistics by aging bucket"""
        domain = []
        if branch_id:
            domain.append(('branch_id', '=', branch_id))
        
        result = {}
        for bucket in ['current', 'due_soon', 'matured', 'grace', 'overdue']:
            bucket_domain = domain + [('aging_bucket', '=', bucket)]
            records = self.search(bucket_domain)
            result[bucket] = {
                'count': len(records),
                'total_principal': sum(records.mapped('principal_amount')),
                'total_due': sum(records.mapped('total_due')),
            }
        
        return result


class PawnInterestPenaltySummary(models.Model):
    """Interest & Penalty Summary Report"""
    _name = 'pawn.interest.penalty.summary'
    _description = 'Interest & Penalty Summary Report'
    _auto = False
    _order = 'date desc'

    date = fields.Date(string='Date', readonly=True)
    branch_id = fields.Many2one('pawn.branch', string='Branch', readonly=True)
    cashier_id = fields.Many2one('res.users', string='Cashier', readonly=True)
    
    # Counts
    renewal_count = fields.Integer(string='Renewals', readonly=True)
    redemption_count = fields.Integer(string='Redemptions', readonly=True)
    
    # Interest
    interest_collected = fields.Monetary(string='Interest Collected', readonly=True, currency_field='currency_id')
    
    # Penalties
    penalty_collected = fields.Monetary(string='Penalty Collected', readonly=True, currency_field='currency_id')
    
    # Service Fees
    service_fee_collected = fields.Monetary(string='Service Fees', readonly=True, currency_field='currency_id')
    
    # Totals
    total_collected = fields.Monetary(string='Total Collected', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    def init(self):
        """Create the view for interest and penalty summary"""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pawn_interest_penalty_summary AS (
                SELECT 
                    ROW_NUMBER() OVER (ORDER BY DATE(pt.write_date), pt.branch_id, pt.write_uid) as id,
                    DATE(pt.write_date) as date,
                    pt.branch_id,
                    pt.write_uid as cashier_id,
                    c.currency_id,
                    
                    -- Count renewals
                    COUNT(CASE WHEN pt.state = 'renewed' THEN 1 END) as renewal_count,
                    
                    -- Count redemptions
                    COUNT(CASE WHEN pt.state = 'redeemed' THEN 1 END) as redemption_count,
                    
                    -- Sum interest collected
                    SUM(pt.interest_amount) as interest_collected,
                    
                    -- Sum penalties collected
                    SUM(pt.penalty_amount) as penalty_collected,
                    
                    -- Sum service fees
                    SUM(pt.service_fee) as service_fee_collected,
                    
                    -- Total collected
                    SUM(pt.interest_amount + pt.penalty_amount + pt.service_fee) as total_collected
                    
                FROM pawn_ticket pt
                LEFT JOIN res_company c ON c.id = pt.company_id
                WHERE pt.state IN ('renewed', 'redeemed')
                    AND pt.write_date >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY DATE(pt.write_date), pt.branch_id, pt.write_uid, c.currency_id
            )
        """)


class PawnTicketRegister(models.Model):
    """Ticket Register Report - All tickets by date/branch/state"""
    _name = 'pawn.ticket.register'
    _description = 'Ticket Register Report'
    _auto = False
    _order = 'date_created desc, ticket_no'

    ticket_id = fields.Many2one('pawn.ticket', string='Ticket', readonly=True)
    ticket_no = fields.Char(string='Ticket No', readonly=True)
    branch_id = fields.Many2one('pawn.branch', string='Branch', readonly=True)
    customer_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    customer_phone = fields.Char(string='Phone', readonly=True)
    
    date_created = fields.Datetime(string='Date Created', readonly=True)
    date_pledged = fields.Date(string='Date Pledged', readonly=True)
    date_maturity = fields.Date(string='Maturity Date', readonly=True)
    date_redeemed = fields.Date(string='Date Redeemed', readonly=True)
    
    principal_amount = fields.Monetary(string='Principal', readonly=True, currency_field='currency_id')
    appraised_value = fields.Monetary(string='Appraised Value', readonly=True, currency_field='currency_id')
    total_due = fields.Monetary(string='Total Due', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('renewed', 'Renewed'),
        ('redeemed', 'Redeemed'),
        ('forfeited', 'Forfeited'),
        ('cancelled', 'Cancelled'),
    ], string='Status', readonly=True)
    
    item_count = fields.Integer(string='Items', readonly=True)
    created_by = fields.Many2one('res.users', string='Created By', readonly=True)

    def init(self):
        """Create the view for ticket register"""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pawn_ticket_register AS (
                SELECT 
                    pt.id as id,
                    pt.id as ticket_id,
                    pt.ticket_no,
                    pt.branch_id,
                    pt.customer_id,
                    rp.phone as customer_phone,
                    pt.date_created,
                    pt.date_pledged,
                    pt.date_maturity,
                    pt.date_redeemed,
                    pt.principal_amount,
                    pt.appraised_value,
                    pt.total_due,
                    c.currency_id,
                    pt.state,
                    pt.create_uid as created_by,
                    (SELECT COUNT(*) FROM pawn_ticket_line WHERE ticket_id = pt.id) as item_count
                    
                FROM pawn_ticket pt
                LEFT JOIN res_partner rp ON rp.id = pt.customer_id
                LEFT JOIN res_company c ON c.id = pt.company_id
                WHERE pt.date_created >= CURRENT_DATE - INTERVAL '365 days'
            )
        """)


class PawnInventoryReport(models.Model):
    """Inventory Report - Items in custody, forfeited, auctioned"""
    _name = 'pawn.inventory.report'
    _description = 'Pawn Inventory Report'
    _auto = False
    _order = 'branch_id, status, category_id'

    branch_id = fields.Many2one('pawn.branch', string='Branch', readonly=True)
    category_id = fields.Many2one('pawn.item.category', string='Category', readonly=True)
    
    status = fields.Selection([
        ('custody', 'In Custody'),
        ('forfeited', 'Forfeited'),
        ('auctioned', 'Auctioned'),
        ('released', 'Released'),
    ], string='Status', readonly=True)
    
    item_count = fields.Integer(string='Item Count', readonly=True)
    total_appraised_value = fields.Monetary(string='Total Appraised Value', readonly=True, currency_field='currency_id')
    total_principal = fields.Monetary(string='Total Principal', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    avg_days_in_custody = fields.Float(string='Avg Days in Custody', readonly=True)

    def init(self):
        """Create the view for inventory report"""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pawn_inventory_report AS (
                SELECT 
                    ROW_NUMBER() OVER (ORDER BY pt.branch_id, 
                        CASE 
                            WHEN pt.state IN ('active', 'renewed') THEN 'custody'
                            WHEN pt.state = 'forfeited' THEN 'forfeited'
                            WHEN pt.state = 'redeemed' THEN 'released'
                            ELSE 'custody'
                        END,
                        ptl.category_id
                    ) as id,
                    pt.branch_id,
                    ptl.category_id,
                    c.currency_id,
                    
                    CASE 
                        WHEN pt.state IN ('active', 'renewed') THEN 'custody'
                        WHEN pt.state = 'forfeited' THEN 'forfeited'
                        WHEN pt.state = 'redeemed' THEN 'released'
                        ELSE 'custody'
                    END as status,
                    
                    COUNT(ptl.id) as item_count,
                    SUM(ptl.appraised_value) as total_appraised_value,
                    SUM(pt.principal_amount) / COUNT(DISTINCT pt.id) as total_principal,
                    AVG(CURRENT_DATE - pt.date_pledged) as avg_days_in_custody
                    
                FROM pawn_ticket pt
                INNER JOIN pawn_ticket_line ptl ON ptl.ticket_id = pt.id
                LEFT JOIN res_company c ON c.id = pt.company_id
                WHERE pt.state IN ('active', 'renewed', 'forfeited', 'redeemed')
                GROUP BY pt.branch_id, ptl.category_id, c.currency_id,
                    CASE 
                        WHEN pt.state IN ('active', 'renewed') THEN 'custody'
                        WHEN pt.state = 'forfeited' THEN 'forfeited'
                        WHEN pt.state = 'redeemed' THEN 'released'
                        ELSE 'custody'
                    END
            )
        """)


class PawnBranchKPI(models.Model):
    """Branch KPI Report - Key performance indicators by branch"""
    _name = 'pawn.branch.kpi'
    _description = 'Branch KPI Report'
    _auto = False
    _order = 'branch_id, period_start desc'

    branch_id = fields.Many2one('pawn.branch', string='Branch', readonly=True)
    period_start = fields.Date(string='Period Start', readonly=True)
    period_end = fields.Date(string='Period End', readonly=True)
    
    # Volume Metrics
    new_tickets = fields.Integer(string='New Tickets', readonly=True)
    renewed_tickets = fields.Integer(string='Renewed Tickets', readonly=True)
    redeemed_tickets = fields.Integer(string='Redeemed Tickets', readonly=True)
    forfeited_tickets = fields.Integer(string='Forfeited Tickets', readonly=True)
    
    # Financial Metrics
    total_principal_disbursed = fields.Monetary(string='Principal Disbursed', readonly=True, currency_field='currency_id')
    total_interest_collected = fields.Monetary(string='Interest Collected', readonly=True, currency_field='currency_id')
    total_penalty_collected = fields.Monetary(string='Penalty Collected', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    # Performance Ratios
    redemption_rate = fields.Float(string='Redemption Rate (%)', readonly=True)
    forfeiture_rate = fields.Float(string='Forfeiture Rate (%)', readonly=True)
    avg_ticket_size = fields.Monetary(string='Avg Ticket Size', readonly=True, currency_field='currency_id')
    avg_days_to_redemption = fields.Float(string='Avg Days to Redemption', readonly=True)

    def init(self):
        """Create the view for branch KPI report"""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pawn_branch_kpi AS (
                SELECT 
                    ROW_NUMBER() OVER (ORDER BY branch_id, period_start DESC) as id,
                    branch_id,
                    period_start,
                    period_end,
                    currency_id,
                    
                    -- Volume metrics
                    COUNT(CASE WHEN state IN ('active', 'renewed', 'redeemed', 'forfeited') THEN 1 END) as new_tickets,
                    COUNT(CASE WHEN state = 'renewed' THEN 1 END) as renewed_tickets,
                    COUNT(CASE WHEN state = 'redeemed' THEN 1 END) as redeemed_tickets,
                    COUNT(CASE WHEN state = 'forfeited' THEN 1 END) as forfeited_tickets,
                    
                    -- Financial metrics
                    SUM(principal_amount) as total_principal_disbursed,
                    SUM(CASE WHEN state IN ('renewed', 'redeemed') THEN interest_amount ELSE 0 END) as total_interest_collected,
                    SUM(CASE WHEN state = 'redeemed' THEN penalty_amount ELSE 0 END) as total_penalty_collected,
                    
                    -- Performance ratios
                    CASE 
                        WHEN COUNT(CASE WHEN state IN ('redeemed', 'forfeited') THEN 1 END) > 0
                        THEN (COUNT(CASE WHEN state = 'redeemed' THEN 1 END)::FLOAT / 
                              COUNT(CASE WHEN state IN ('redeemed', 'forfeited') THEN 1 END)::FLOAT * 100)
                        ELSE 0
                    END as redemption_rate,
                    
                    CASE 
                        WHEN COUNT(CASE WHEN state IN ('redeemed', 'forfeited') THEN 1 END) > 0
                        THEN (COUNT(CASE WHEN state = 'forfeited' THEN 1 END)::FLOAT / 
                              COUNT(CASE WHEN state IN ('redeemed', 'forfeited') THEN 1 END)::FLOAT * 100)
                        ELSE 0
                    END as forfeiture_rate,
                    
                    AVG(principal_amount) as avg_ticket_size,
                    AVG(CASE WHEN state = 'redeemed' THEN (date_redeemed - date_pledged) END) as avg_days_to_redemption
                    
                FROM (
                    SELECT 
                        pt.*,
                        c.currency_id,
                        DATE_TRUNC('month', pt.date_created)::DATE as period_start,
                        (DATE_TRUNC('month', pt.date_created) + INTERVAL '1 month - 1 day')::DATE as period_end
                    FROM pawn_ticket pt
                    LEFT JOIN res_company c ON c.id = pt.company_id
                    WHERE pt.date_created >= CURRENT_DATE - INTERVAL '12 months'
                ) as tickets
                GROUP BY branch_id, period_start, period_end, currency_id
            )
        """)
