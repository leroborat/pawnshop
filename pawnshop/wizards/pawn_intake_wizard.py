# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class PawnIntakeWizard(models.TransientModel):
    """
    Multi-step wizard for creating new pawn tickets.
    Guides cashiers through: Customer → Items → Appraisal → Rate → Preview
    """
    _name = 'pawn.intake.wizard'
    _description = 'Pawn Ticket Intake Wizard'

    # ============================================================
    # WIZARD CONTROL
    # ============================================================

    current_step = fields.Selection([
        ('customer', 'Customer Information'),
        ('kyc', 'KYC & Documents'),
        ('items', 'Item Details'),
        ('appraisal', 'Appraisal & Valuation'),
        ('rate', 'Rate & Loan Terms'),
        ('preview', 'Preview & Confirm'),
    ], string='Current Step', default='customer', required=True)

    # ============================================================
    # STEP 1: CUSTOMER INFORMATION
    # ============================================================

    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        domain=[('customer_rank', '>', 0)],
        help="Select existing customer or create new"
    )
    branch_id = fields.Many2one(
        'pawn.branch',
        string='Branch',
        required=True,
        default=lambda self: self._default_branch(),
        help="Branch where ticket is created"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )

    # ============================================================
    # STEP 2: KYC & DOCUMENTS
    # ============================================================

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
    ], string='ID Type', help="Type of ID presented")

    kyc_id_number = fields.Char(
        string='ID Number',
        help="ID card number"
    )
    kyc_id_expiry = fields.Date(
        string='ID Expiry Date',
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

    # ============================================================
    # STEP 3 & 4: ITEMS (via One2many)
    # ============================================================

    line_ids = fields.One2many(
        'pawn.intake.wizard.line',
        'wizard_id',
        string='Pawned Items',
        help="Items being pledged as collateral"
    )

    item_count = fields.Integer(
        string='Item Count',
        compute='_compute_item_count',
        help="Total number of items"
    )

    # ============================================================
    # STEP 5: RATE & LOAN TERMS
    # ============================================================

    date_maturity = fields.Date(
        string='Maturity Date',
        required=True,
        default=lambda self: fields.Date.today() + timedelta(days=30),
        help="Date when loan must be renewed or redeemed"
    )
    interest_rate = fields.Float(
        string='Interest Rate (%)',
        required=True,
        digits=(5, 2),
        default=lambda self: self._default_interest_rate(),
        help="Monthly interest rate"
    )
    principal_amount = fields.Monetary(
        string='Principal Amount',
        required=True,
        currency_field='currency_id',
        help="Loan amount to disburse"
    )

    # Computed Totals
    appraised_value = fields.Monetary(
        string='Total Appraised Value',
        compute='_compute_totals',
        currency_field='currency_id',
        help="Sum of all item appraised values"
    )
    ltv_ratio = fields.Float(
        string='LTV Ratio (%)',
        compute='_compute_totals',
        digits=(5, 2),
        help="Loan-to-Value ratio"
    )
    interest_amount = fields.Monetary(
        string='Estimated Interest (1 month)',
        compute='_compute_totals',
        currency_field='currency_id',
        help="Interest for one maturity period"
    )
    total_due_at_maturity = fields.Monetary(
        string='Total Due at Maturity',
        compute='_compute_totals',
        currency_field='currency_id',
        help="Principal + Interest"
    )

    # ============================================================
    # STEP 6: PREVIEW & NOTES
    # ============================================================

    notes = fields.Text(
        string='Notes',
        help="Additional notes or special instructions"
    )
    terms_accepted = fields.Boolean(
        string='Terms & Conditions Accepted',
        help="Customer has read and accepted terms"
    )

    # ============================================================
    # COMPUTE METHODS
    # ============================================================

    @api.model
    def _default_branch(self):
        """Get user's default branch or first available"""
        user = self.env.user
        if hasattr(user, 'branch_ids') and user.branch_ids:
            return user.branch_ids[0].id
        return self.env['pawn.branch'].search([('active', '=', True)], limit=1).id

    @api.model
    def _default_interest_rate(self):
        """Get default interest rate from settings"""
        return float(self.env['ir.config_parameter'].sudo().get_param(
            'pawnshop.default_interest_rate', '3.5'
        ))

    @api.depends('line_ids')
    def _compute_item_count(self):
        for wizard in self:
            wizard.item_count = len(wizard.line_ids)

    @api.depends('line_ids.appraised_value', 'principal_amount', 'interest_rate')
    def _compute_totals(self):
        for wizard in self:
            wizard.appraised_value = sum(line.appraised_value for line in wizard.line_ids)
            if wizard.appraised_value > 0:
                wizard.ltv_ratio = (wizard.principal_amount / wizard.appraised_value) * 100
            else:
                wizard.ltv_ratio = 0.0
            wizard.interest_amount = wizard.principal_amount * (wizard.interest_rate / 100)
            wizard.total_due_at_maturity = wizard.principal_amount + wizard.interest_amount

    # ============================================================
    # NAVIGATION METHODS
    # ============================================================

    def action_next_step(self):
        """Move to next step in wizard"""
        self.ensure_one()

        step_order = ['customer', 'kyc', 'items', 'appraisal', 'rate', 'preview']
        current_index = step_order.index(self.current_step)

        # Validate current step before proceeding
        self._validate_step(self.current_step)

        if current_index < len(step_order) - 1:
            self.current_step = step_order[current_index + 1]

        return self._reopen_wizard()

    def action_previous_step(self):
        """Move to previous step in wizard"""
        self.ensure_one()

        step_order = ['customer', 'kyc', 'items', 'appraisal', 'rate', 'preview']
        current_index = step_order.index(self.current_step)

        if current_index > 0:
            self.current_step = step_order[current_index - 1]

        return self._reopen_wizard()

    def action_jump_to_step(self, step):
        """Jump directly to a specific step"""
        self.ensure_one()
        self.current_step = step
        return self._reopen_wizard()

    def _reopen_wizard(self):
        """Return action to reopen wizard in same window"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ============================================================
    # VALIDATION METHODS
    # ============================================================

    def _validate_step(self, step):
        """Validate data for the current step"""
        self.ensure_one()

        if step == 'customer':
            if not self.customer_id:
                raise UserError(_('Please select a customer.'))
            if not self.branch_id:
                raise UserError(_('Please select a branch.'))

        elif step == 'kyc':
            # KYC is optional but warn if missing
            if not self.kyc_id_type:
                # Could add warning here
                pass

        elif step == 'items':
            if not self.line_ids:
                raise UserError(_('Please add at least one item.'))

        elif step == 'appraisal':
            for line in self.line_ids:
                if line.appraised_value <= 0:
                    raise UserError(_('All items must have an appraised value greater than zero.'))

        elif step == 'rate':
            if self.principal_amount <= 0:
                raise UserError(_('Principal amount must be greater than zero.'))
            if not self.interest_rate or self.interest_rate < 0:
                raise UserError(_('Interest rate must be a positive number.'))
            if not self.date_maturity:
                raise UserError(_('Maturity date is required.'))
            if self.date_maturity <= fields.Date.today():
                raise UserError(_('Maturity date must be in the future.'))

            # Check LTV ratio
            max_ltv = float(self.env['ir.config_parameter'].sudo().get_param(
                'pawnshop.max_ltv_ratio', '80.0'
            ))
            if self.ltv_ratio > max_ltv:
                raise UserError(_(
                    'LTV ratio (%.2f%%) exceeds maximum allowed (%.2f%%). '
                    'Please reduce principal amount or increase item values.'
                ) % (self.ltv_ratio, max_ltv))

        elif step == 'preview':
            if not self.terms_accepted:
                raise UserError(_('Customer must accept terms and conditions before proceeding.'))

    # ============================================================
    # FINAL ACTION: CREATE TICKET
    # ============================================================

    def action_create_ticket(self):
        """Create the pawn ticket from wizard data"""
        self.ensure_one()

        # Final validation
        self._validate_step('preview')

        # Prepare ticket values
        ticket_vals = {
            'customer_id': self.customer_id.id,
            'branch_id': self.branch_id.id,
            'company_id': self.company_id.id,
            'date_maturity': self.date_maturity,
            'principal_amount': self.principal_amount,
            'interest_rate': self.interest_rate,
            'kyc_id_type': self.kyc_id_type,
            'kyc_id_number': self.kyc_id_number,
            'kyc_id_expiry': self.kyc_id_expiry,
            'kyc_photo': self.kyc_photo,
            'kyc_id_photo_front': self.kyc_id_photo_front,
            'kyc_id_photo_back': self.kyc_id_photo_back,
            'state': 'draft',
            'line_ids': [(0, 0, {
                'name': line.name,
                'category_id': line.category_id.id,
                'brand': line.brand,
                'model': line.model,
                'serial_number': line.serial_number,
                'color': line.color,
                'condition': line.condition,
                'weight': line.weight,
                'weight_unit': line.weight_unit,
                'karat': line.karat,
                'appraised_value': line.appraised_value,
                'photo_1': line.photo_1,
                'photo_2': line.photo_2,
                'photo_3': line.photo_3,
                'photo_4': line.photo_4,
                'appraisal_notes': line.appraisal_notes,
            }) for line in self.line_ids],
        }

        # Add notes if provided
        if self.notes:
            ticket_vals['note'] = self.notes

        # Create ticket
        ticket = self.env['pawn.ticket'].create(ticket_vals)

        # Open the created ticket
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pawn Ticket'),
            'res_model': 'pawn.ticket',
            'res_id': ticket.id,
            'view_mode': 'form',
            'target': 'current',
        }


class PawnIntakeWizardLine(models.TransientModel):
    """
    Line items for intake wizard (items being pledged)
    """
    _name = 'pawn.intake.wizard.line'
    _description = 'Pawn Intake Wizard Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'pawn.intake.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(string='Sequence', default=10)

    # Item Identification
    name = fields.Char(
        string='Item Description',
        required=True,
        help="Detailed description of the pawned item"
    )
    category_id = fields.Many2one(
        'pawn.item.category',
        string='Category',
        required=True,
        ondelete='restrict',
        help="Item category (Jewelry, Electronics, etc.)"
    )

    # Specifications
    brand = fields.Char(string='Brand')
    model = fields.Char(string='Model')
    serial_number = fields.Char(string='Serial Number')
    color = fields.Char(string='Color')
    condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Condition', default='good')

    weight = fields.Float(string='Weight', digits=(10, 3))
    weight_unit = fields.Selection([
        ('g', 'Grams'),
        ('kg', 'Kilograms'),
        ('oz', 'Ounces'),
    ], string='Weight Unit', default='g')

    karat = fields.Selection([
        ('8k', '8 Karat'),
        ('10k', '10 Karat'),
        ('14k', '14 Karat'),
        ('18k', '18 Karat'),
        ('21k', '21 Karat'),
        ('22k', '22 Karat'),
        ('24k', '24 Karat'),
        ('925', '925 Sterling Silver'),
        ('999', '999 Fine Silver'),
    ], string='Purity/Karat')

    # Valuation
    appraised_value = fields.Monetary(
        string='Appraised Value',
        required=True,
        currency_field='currency_id',
        help="Estimated market value"
    )

    # Related
    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.currency_id',
        readonly=True,
    )

    # Photos
    photo_1 = fields.Binary(string='Photo 1', attachment=True)
    photo_2 = fields.Binary(string='Photo 2', attachment=True)
    photo_3 = fields.Binary(string='Photo 3', attachment=True)
    photo_4 = fields.Binary(string='Photo 4', attachment=True)

    # Appraisal Details
    appraisal_notes = fields.Text(string='Appraisal Notes')
