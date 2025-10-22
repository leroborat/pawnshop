# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PawnRateTable(models.Model):
    """
    Interest rate configuration table
    Supports tiered rates based on loan amount ranges and item categories
    """
    _name = 'pawn.rate.table'
    _description = 'Pawn Rate Table'
    _order = 'sequence, name'

    # Basic Information
    name = fields.Char(
        string='Rate Table Name',
        required=True,
        help="Name for this rate table (e.g., 'Standard 2025', 'Promotional Rates')"
    )
    code = fields.Char(
        string='Code',
        required=True,
        size=10,
        help="Short code for reference"
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Only active rate tables can be used for new tickets"
    )

    # Validity Period
    date_from = fields.Date(
        string='Valid From',
        required=True,
        default=fields.Date.context_today,
        help="Start date for this rate table"
    )
    date_to = fields.Date(
        string='Valid To',
        help="End date for this rate table (leave empty for indefinite)"
    )

    # Configuration
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    branch_ids = fields.Many2many(
        'pawn.branch',
        string='Applicable Branches',
        help="Leave empty to apply to all branches"
    )

    # Rate Lines
    line_ids = fields.One2many(
        'pawn.rate.table.line',
        'rate_table_id',
        string='Rate Lines',
        help="Rate tiers based on loan amount and/or category"
    )

    # Description
    notes = fields.Text(
        string='Notes',
        help="Additional information about this rate table"
    )

    # SQL Constraints
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code, company_id)', 'Rate table code must be unique per company!'),
    ]

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        """Ensure date_to is after date_from"""
        for record in self:
            if record.date_to and record.date_from and record.date_to < record.date_from:
                raise ValidationError(_('End date must be after start date.'))

    def get_applicable_rate(self, loan_amount, category_id=None, branch_id=None, date=None):
        """
        Get the applicable interest rate for given parameters
        Returns the rate percentage (e.g., 3.5 for 3.5% per month)
        """
        self.ensure_one()
        if date is None:
            date = fields.Date.context_today(self)

        # Check if rate table is valid for the date
        if date < self.date_from or (self.date_to and date > self.date_to):
            return False

        # Find matching line
        applicable_lines = self.line_ids.filtered(
            lambda l: (
                l.amount_from <= loan_amount and
                (not l.amount_to or loan_amount <= l.amount_to) and
                (not l.category_id or l.category_id.id == category_id) and
                (not l.branch_id or l.branch_id.id == branch_id)
            )
        )

        if not applicable_lines:
            return False

        # Return the most specific match (with category/branch filters takes precedence)
        sorted_lines = applicable_lines.sorted(
            key=lambda l: (bool(l.category_id), bool(l.branch_id)),
            reverse=True
        )
        return sorted_lines[0].rate_percent

    def name_get(self):
        """Display as [CODE] Name"""
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}"
            result.append((record.id, name))
        return result


class PawnRateTableLine(models.Model):
    """
    Individual rate tiers within a rate table
    Allows flexible rate configuration based on amount ranges and categories
    """
    _name = 'pawn.rate.table.line'
    _description = 'Pawn Rate Table Line'
    _order = 'rate_table_id, sequence, amount_from'

    # Header Reference
    rate_table_id = fields.Many2one(
        'pawn.rate.table',
        string='Rate Table',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    # Filters
    category_id = fields.Many2one(
        'pawn.item.category',
        string='Item Category',
        help="Apply this rate only to specific category (leave empty for all)"
    )
    branch_id = fields.Many2one(
        'pawn.branch',
        string='Branch',
        help="Apply this rate only to specific branch (leave empty for all)"
    )

    # Amount Range
    amount_from = fields.Monetary(
        string='Amount From',
        required=True,
        default=0.0,
        currency_field='currency_id',
        help="Minimum loan amount for this rate tier"
    )
    amount_to = fields.Monetary(
        string='Amount To',
        currency_field='currency_id',
        help="Maximum loan amount for this rate tier (leave empty for unlimited)"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Rate
    rate_percent = fields.Float(
        string='Interest Rate (%)',
        required=True,
        digits=(5, 2),
        help="Interest rate per period (e.g., 3.5 for 3.5% per month)"
    )
    rate_period = fields.Selection(
        [
            ('month', 'Per Month'),
            ('day', 'Per Day'),
            ('year', 'Per Year'),
        ],
        string='Rate Period',
        default='month',
        required=True,
        help="Time period for interest calculation"
    )

    # Description
    name = fields.Char(
        string='Description',
        compute='_compute_name',
        store=True,
        help="Auto-generated description of this rate line"
    )

    # SQL Constraints
    _sql_constraints = [
        ('rate_positive', 'CHECK(rate_percent >= 0)', 'Interest rate must be positive or zero!'),
        ('amount_from_positive', 'CHECK(amount_from >= 0)', 'Amount from must be positive or zero!'),
    ]

    @api.depends('amount_from', 'amount_to', 'rate_percent', 'category_id', 'branch_id')
    def _compute_name(self):
        """Generate descriptive name for the rate line"""
        for record in self:
            parts = []

            # Amount range
            if record.amount_to:
                parts.append(f"{record.amount_from:,.0f} - {record.amount_to:,.0f}")
            else:
                parts.append(f"{record.amount_from:,.0f}+")

            # Rate
            parts.append(f"@ {record.rate_percent}% / {dict(record._fields['rate_period'].selection).get(record.rate_period, 'month')}")

            # Filters
            if record.category_id:
                parts.append(f"({record.category_id.name})")
            if record.branch_id:
                parts.append(f"[{record.branch_id.code}]")

            record.name = " ".join(parts)

    @api.constrains('amount_from', 'amount_to')
    def _check_amount_range(self):
        """Ensure amount_to is greater than amount_from"""
        for record in self:
            if record.amount_to and record.amount_to <= record.amount_from:
                raise ValidationError(_('Amount To must be greater than Amount From.'))

    @api.constrains('rate_table_id', 'amount_from', 'amount_to', 'category_id', 'branch_id')
    def _check_overlapping_ranges(self):
        """Prevent overlapping amount ranges for same category/branch combination"""
        for record in self:
            domain = [
                ('rate_table_id', '=', record.rate_table_id.id),
                ('id', '!=', record.id),
                ('category_id', '=', record.category_id.id if record.category_id else False),
                ('branch_id', '=', record.branch_id.id if record.branch_id else False),
            ]

            overlapping = self.search(domain).filtered(
                lambda l: (
                    # Check if ranges overlap
                    (not l.amount_to or l.amount_to >= record.amount_from) and
                    (not record.amount_to or record.amount_to >= l.amount_from)
                )
            )

            if overlapping:
                raise ValidationError(_(
                    'Amount ranges cannot overlap for the same category and branch combination. '
                    'Conflicting with: %s'
                ) % overlapping[0].name)
