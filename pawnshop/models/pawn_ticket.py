# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from datetime import datetime, date


class PawnTicket(models.Model):
    """
    Main pawn ticket model representing a loan secured by collateral items.
    Manages the complete lifecycle from pledging to redemption/forfeiture.
    """
    _name = 'pawn.ticket'
    _description = 'Pawn Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_created desc, ticket_no desc'
    _check_company_auto = True

    # ============================================================
    # HEADER FIELDS
    # ============================================================

    # Identification
    ticket_no = fields.Char(
        string='Ticket Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        tracking=True,
        help="Unique ticket identifier, auto-generated from sequence"
    )

    name = fields.Char(
        string='Ticket Reference',
        compute='_compute_name',
        store=True,
        index=True,
    )

    # Customer Information
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help="Customer who pledged the items"
    )

    # Branch & Company
    branch_id = fields.Many2one(
        'pawn.branch',
        string='Branch',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help="Branch where this ticket was created"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )

    # Dates
    date_created = fields.Datetime(
        string='Date Created',
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
        help="Date and time when ticket was created"
    )
    date_pledged = fields.Date(
        string='Date Pledged',
        readonly=True,
        copy=False,
        tracking=True,
        help="Date when loan was disbursed"
    )
    date_maturity = fields.Date(
        string='Maturity Date',
        required=True,
        tracking=True,
        help="Date when loan must be renewed or redeemed"
    )
    date_grace_end = fields.Date(
        string='Grace Period End',
        compute='_compute_date_grace_end',
        store=True,
        help="Last date before automatic forfeiture"
    )
    date_renewed = fields.Date(
        string='Last Renewal Date',
        readonly=True,
        copy=False,
        tracking=True,
        help="Date of most recent renewal"
    )
    date_redeemed = fields.Date(
        string='Date Redeemed',
        readonly=True,
        copy=False,
        tracking=True,
        help="Date when items were redeemed"
    )
    date_forfeited = fields.Date(
        string='Date Forfeited',
        readonly=True,
        copy=False,
        tracking=True,
        help="Date when items were forfeited"
    )

    # Financial Fields
    principal_amount = fields.Monetary(
        string='Principal Amount',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help="Loan amount disbursed to customer"
    )
    appraised_value = fields.Monetary(
        string='Total Appraised Value',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
        help="Sum of all item appraised values"
    )
    interest_rate = fields.Float(
        string='Interest Rate (%)',
        required=True,
        digits=(5, 2),
        tracking=True,
        help="Interest rate per month"
    )
    interest_amount = fields.Monetary(
        string='Interest Amount',
        compute='_compute_interest_penalty',
        store=True,
        currency_field='currency_id',
        help="Computed interest charges"
    )
    penalty_amount = fields.Monetary(
        string='Penalty Amount',
        compute='_compute_interest_penalty',
        store=True,
        currency_field='currency_id',
        help="Computed penalty charges for overdue"
    )
    service_fee = fields.Monetary(
        string='Service Fee',
        compute='_compute_service_fee',
        store=True,
        currency_field='currency_id',
        help="Service fee for this transaction"
    )
    total_due = fields.Monetary(
        string='Total Amount Due',
        compute='_compute_total_due',
        store=True,
        currency_field='currency_id',
        help="Total amount to redeem (principal + interest + penalty + service fee)"
    )
    ltv_ratio = fields.Float(
        string='LTV Ratio (%)',
        compute='_compute_ltv_ratio',
        store=True,
        digits=(5, 2),
        help="Loan-to-Value ratio (Principal / Appraised Value * 100)"
    )

    # State Management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pledged', 'Pledged'),
        ('renewed', 'Renewed'),
        ('redeemed', 'Redeemed'),
        ('forfeited', 'Forfeited'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True, copy=False,
       help="Ticket lifecycle status")

    # Status Indicators (for UI)
    status_color = fields.Integer(
        string='Status Color',
        compute='_compute_status_indicators',
        help="Color indicator for kanban view"
    )
    days_to_maturity = fields.Integer(
        string='Days to Maturity',
        compute='_compute_status_indicators',
        help="Days until maturity date (negative if overdue)"
    )
    is_due_today = fields.Boolean(
        string='Due Today',
        compute='_compute_status_indicators',
        search='_search_due_today',
        help="Ticket matures today"
    )
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_status_indicators',
        search='_search_overdue',
        help="Past maturity date"
    )
    is_in_grace = fields.Boolean(
        string='In Grace Period',
        compute='_compute_status_indicators',
        search='_search_in_grace',
        help="Past maturity but within grace period"
    )

    # KYC Fields
    kyc_id_type = fields.Selection([
        ('passport', 'Passport'),
        ('drivers_license', "Driver's License"),
        ('national_id', 'National ID'),
        ('umid', 'UMID'),
        ('postal_id', 'Postal ID'),
        ('voters_id', "Voter's ID"),
        ('senior_citizen', 'Senior Citizen ID'),
        ('pwd_id', 'PWD ID'),
        ('other', 'Other'),
    ], string='ID Type', tracking=True, help="Type of ID presented")

    kyc_id_number = fields.Char(
        string='ID Number',
        tracking=True,
        help="ID card number"
    )
    kyc_id_expiry = fields.Date(
        string='ID Expiry Date',
        tracking=True,
        help="Expiration date of ID"
    )
    kyc_photo = fields.Binary(
        string='Customer Photo',
        attachment=True,
        help="Photo of customer"
    )
    kyc_id_photo_front = fields.Binary(
        string='ID Photo (Front)',
        attachment=True,
        help="Front side of ID"
    )
    kyc_id_photo_back = fields.Binary(
        string='ID Photo (Back)',
        attachment=True,
        help="Back side of ID"
    )

    # Disbursement Tracking (Community Edition - no accounting integration)
    disbursement_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('gcash', 'GCash'),
        ('maya', 'Maya'),
        ('other', 'Other'),
    ], string='Disbursement Method', tracking=True, help="How loan was disbursed")

    disbursement_reference = fields.Char(
        string='Disbursement Reference',
        tracking=True,
        help="Transaction reference number (for non-cash disbursements)"
    )
    disbursement_date = fields.Datetime(
        string='Disbursement Date/Time',
        readonly=True,
        copy=False,
        help="When funds were actually disbursed"
    )
    disbursed_by = fields.Many2one(
        'res.users',
        string='Disbursed By',
        readonly=True,
        copy=False,
        help="User who disbursed the funds"
    )

    # Relations
    line_ids = fields.One2many(
        'pawn.ticket.line',
        'ticket_id',
        string='Pawned Items',
        copy=True,
        help="Items pledged as collateral"
    )
    rate_table_id = fields.Many2one(
        'pawn.rate.table',
        string='Rate Table',
        tracking=True,
        help="Rate table used for interest calculation"
    )

    # Invoice Tracking
    invoice_ids = fields.Many2many(
        'account.move',
        string='Invoices',
        copy=False,
        help="Related invoices (renewals, redemptions)"
    )
    invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_invoice_count',
    )

    # Notes
    notes = fields.Text(
        string='Internal Notes',
        help="Internal notes not visible to customer"
    )
    terms_accepted = fields.Boolean(
        string='Terms Accepted',
        help="Customer accepted terms and conditions"
    )

    # ============================================================
    # COMPUTED FIELDS
    # ============================================================

    @api.depends('ticket_no', 'customer_id.name')
    def _compute_name(self):
        """Compute display name"""
        for record in self:
            if record.ticket_no and record.ticket_no != 'New':
                record.name = f"{record.ticket_no} - {record.customer_id.name or ''}"
            else:
                record.name = _('New Ticket')

    @api.depends('line_ids.appraised_value')
    def _compute_amounts(self):
        """Compute total appraised value from line items"""
        for record in self:
            record.appraised_value = sum(record.line_ids.mapped('appraised_value'))

    @api.depends('principal_amount', 'appraised_value')
    def _compute_ltv_ratio(self):
        """Compute loan-to-value ratio"""
        for record in self:
            if record.appraised_value > 0:
                record.ltv_ratio = (record.principal_amount / record.appraised_value) * 100
            else:
                record.ltv_ratio = 0.0

    @api.depends('date_maturity')
    def _compute_date_grace_end(self):
        """Compute grace period end date"""
        grace_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'pawnshop.grace_period_days', default=7
        ))
        for record in self:
            if record.date_maturity:
                record.date_grace_end = record.date_maturity + relativedelta(days=grace_days)
            else:
                record.date_grace_end = False

    @api.depends('principal_amount', 'interest_rate', 'date_pledged', 'date_maturity', 'state')
    def _compute_interest_penalty(self):
        """Compute interest and penalty amounts"""
        for record in self:
            if record.state in ('draft', 'cancelled'):
                record.interest_amount = 0.0
                record.penalty_amount = 0.0
                continue

            # Interest calculation
            if record.date_pledged and record.date_maturity:
                days = (record.date_maturity - record.date_pledged).days
                months = days / 30.0  # Approximate
                record.interest_amount = record.principal_amount * (record.interest_rate / 100) * months
            else:
                record.interest_amount = 0.0

            # Penalty calculation (only if overdue)
            if record.is_overdue and record.date_maturity:
                penalty_rate = float(self.env['ir.config_parameter'].sudo().get_param(
                    'pawnshop.penalty_rate_percent', default=3.0
                ))
                overdue_days = (date.today() - record.date_maturity).days
                penalty_months = overdue_days / 30.0
                record.penalty_amount = record.principal_amount * (penalty_rate / 100) * penalty_months
            else:
                record.penalty_amount = 0.0

    @api.depends('principal_amount')
    def _compute_service_fee(self):
        """Compute service fee based on configuration"""
        for record in self:
            fee_type = self.env['ir.config_parameter'].sudo().get_param(
                'pawnshop.service_fee_type', default='percent'
            )

            if fee_type == 'fixed':
                record.service_fee = float(self.env['ir.config_parameter'].sudo().get_param(
                    'pawnshop.service_fee_amount', default=0.0
                ))
            elif fee_type == 'percent':
                fee_percent = float(self.env['ir.config_parameter'].sudo().get_param(
                    'pawnshop.service_fee_percent', default=1.0
                ))
                record.service_fee = record.principal_amount * (fee_percent / 100)
            elif fee_type == 'both':
                fee_percent = float(self.env['ir.config_parameter'].sudo().get_param(
                    'pawnshop.service_fee_percent', default=1.0
                ))
                fee_fixed = float(self.env['ir.config_parameter'].sudo().get_param(
                    'pawnshop.service_fee_amount', default=0.0
                ))
                record.service_fee = (record.principal_amount * (fee_percent / 100)) + fee_fixed
            else:
                record.service_fee = 0.0

    @api.depends('principal_amount', 'interest_amount', 'penalty_amount', 'service_fee', 'state')
    def _compute_total_due(self):
        """Compute total amount due for redemption"""
        for record in self:
            if record.state in ('redeemed', 'forfeited', 'cancelled'):
                record.total_due = 0.0
            else:
                record.total_due = (
                    record.principal_amount +
                    record.interest_amount +
                    record.penalty_amount +
                    record.service_fee
                )

    @api.depends('date_maturity', 'date_grace_end', 'state')
    def _compute_status_indicators(self):
        """Compute status indicators for UI"""
        today = date.today()
        for record in self:
            # Days to maturity
            if record.date_maturity:
                record.days_to_maturity = (record.date_maturity - today).days
            else:
                record.days_to_maturity = 0

            # Status flags
            if record.state in ('draft', 'cancelled'):
                record.is_due_today = False
                record.is_overdue = False
                record.is_in_grace = False
                record.status_color = 0
            elif record.state in ('redeemed', 'forfeited'):
                record.is_due_today = False
                record.is_overdue = False
                record.is_in_grace = False
                record.status_color = 10  # Gray
            else:
                # Active tickets
                record.is_due_today = record.date_maturity == today
                record.is_overdue = record.date_maturity < today if record.date_maturity else False
                record.is_in_grace = (
                    record.is_overdue and
                    record.date_grace_end >= today if record.date_grace_end else False
                )

                # Color coding
                if record.days_to_maturity < 0:
                    if record.is_in_grace:
                        record.status_color = 9  # Orange - in grace period
                    else:
                        record.status_color = 1  # Red - past grace period
                elif record.days_to_maturity == 0:
                    record.status_color = 2  # Yellow - due today
                elif record.days_to_maturity <= 3:
                    record.status_color = 3  # Light orange - due soon
                else:
                    record.status_color = 10  # Green - current

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        """Count related invoices"""
        for record in self:
            record.invoice_count = len(record.invoice_ids)

    # ============================================================
    # SEARCH METHODS
    # ============================================================

    def _search_due_today(self, operator, value):
        """Search for tickets due today"""
        today = date.today()
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('date_maturity', '=', today), ('state', 'in', ('pledged', 'renewed'))]
        else:
            return [('date_maturity', '!=', today)]

    def _search_overdue(self, operator, value):
        """Search for overdue tickets"""
        today = date.today()
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('date_maturity', '<', today), ('state', 'in', ('pledged', 'renewed'))]
        else:
            return [('date_maturity', '>=', today)]

    def _search_in_grace(self, operator, value):
        """Search for tickets in grace period"""
        today = date.today()
        grace_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'pawnshop.grace_period_days', default=7
        ))
        grace_start = today - relativedelta(days=grace_days)

        if (operator == '=' and value) or (operator == '!=' and not value):
            return [
                ('date_maturity', '>=', grace_start),
                ('date_maturity', '<', today),
                ('state', 'in', ('pledged', 'renewed'))
            ]
        else:
            return ['|', ('date_maturity', '<', grace_start), ('date_maturity', '>=', today)]

    # ============================================================
    # CRUD METHODS
    # ============================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Generate ticket number from sequence"""
        for vals in vals_list:
            if vals.get('ticket_no', _('New')) == _('New'):
                branch = self.env['pawn.branch'].browse(vals.get('branch_id'))
                if branch and branch.ticket_sequence_id:
                    vals['ticket_no'] = branch.ticket_sequence_id.next_by_id()
                else:
                    raise UserError(_('Please configure ticket sequence for branch %s') % branch.name)
        return super().create(vals_list)

    # ============================================================
    # CONSTRAINTS
    # ============================================================

    @api.constrains('principal_amount', 'appraised_value')
    def _check_ltv_ratio(self):
        """Validate loan-to-value ratio"""
        max_ltv = float(self.env['ir.config_parameter'].sudo().get_param(
            'pawnshop.max_ltv_ratio', default=80.0
        ))
        for record in self:
            if record.ltv_ratio > max_ltv:
                raise ValidationError(_(
                    'LTV ratio (%.2f%%) exceeds maximum allowed (%.2f%%).'
                ) % (record.ltv_ratio, max_ltv))

    @api.constrains('principal_amount')
    def _check_loan_amount_limits(self):
        """Validate loan amount within configured limits"""
        min_amount = float(self.env['ir.config_parameter'].sudo().get_param(
            'pawnshop.min_loan_amount', default=100.0
        ))
        max_amount = float(self.env['ir.config_parameter'].sudo().get_param(
            'pawnshop.max_loan_amount', default=500000.0
        ))

        for record in self:
            if record.principal_amount < min_amount:
                raise ValidationError(_(
                    'Principal amount must be at least %.2f'
                ) % min_amount)
            if max_amount > 0 and record.principal_amount > max_amount:
                raise ValidationError(_(
                    'Principal amount cannot exceed %.2f'
                ) % max_amount)

    @api.constrains('line_ids')
    def _check_has_items(self):
        """Ensure ticket has at least one item"""
        for record in self:
            if record.state != 'draft' and not record.line_ids:
                raise ValidationError(_('Ticket must have at least one pawned item.'))

    # ============================================================
    # ACTION METHODS (Workflows)
    # ============================================================

    def action_disburse(self):
        """Mark ticket as pledged and record disbursement"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft tickets can be disbursed.'))

        self.write({
            'state': 'pledged',
            'date_pledged': date.today(),
            'disbursement_date': fields.Datetime.now(),
            'disbursed_by': self.env.user.id,
        })

        # Create stock moves for items (will be implemented with inventory integration)
        for line in self.line_ids:
            line._create_stock_move()

        return True

    def action_renew(self):
        """Renew ticket - extends maturity date"""
        # Will be implemented as a wizard in Phase 5
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Renew Ticket'),
            'res_model': 'pawn.renew.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_id': self.id},
        }

    def action_redeem(self):
        """Redeem ticket - customer pays and retrieves items"""
        # Will be implemented as a wizard in Phase 5
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Redeem Ticket'),
            'res_model': 'pawn.redeem.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_id': self.id},
        }

    def action_forfeit(self):
        """Forfeit ticket - items become company property"""
        self.ensure_one()
        if self.state not in ('pledged', 'renewed'):
            raise UserError(_('Only active tickets can be forfeited.'))

        if not self.is_overdue:
            raise UserError(_('Cannot forfeit ticket that is not overdue.'))

        # Check grace period
        if self.is_in_grace:
            raise UserError(_('Cannot forfeit during grace period.'))

        self.write({
            'state': 'forfeited',
            'date_forfeited': date.today(),
        })

        # Move items to forfeited inventory
        for line in self.line_ids:
            line._forfeit_item()

        return True

    def action_cancel(self):
        """Cancel draft ticket"""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft tickets can be cancelled.'))
            record.state = 'cancelled'

    def action_view_invoices(self):
        """View related invoices"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'default_partner_id': self.customer_id.id},
        }
