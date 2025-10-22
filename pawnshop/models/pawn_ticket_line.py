# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class PawnTicketLine(models.Model):
    """
    Individual items pledged as collateral on a pawn ticket.
    Each line represents one item with photos, description, and valuation.
    """
    _name = 'pawn.ticket.line'
    _description = 'Pawn Ticket Line (Pawned Item)'
    _order = 'sequence, id'

    # ============================================================
    # FIELDS
    # ============================================================

    # Basic Info
    ticket_id = fields.Many2one(
        'pawn.ticket',
        string='Pawn Ticket',
        required=True,
        ondelete='cascade',
        index=True,
        help="Parent pawn ticket"
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Display order"
    )

    # Item Identification
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        ondelete='restrict',
        help="Product template for this item (optional, for standardized items)"
    )
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
    brand = fields.Char(
        string='Brand',
        help="Item brand/manufacturer"
    )
    model = fields.Char(
        string='Model',
        help="Model number or name"
    )
    serial_number = fields.Char(
        string='Serial Number',
        help="Serial number, IMEI, or unique identifier"
    )
    color = fields.Char(
        string='Color',
        help="Item color"
    )
    condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Condition', default='good', help="Physical condition of item")

    weight = fields.Float(
        string='Weight',
        digits=(10, 3),
        help="Weight in grams (for jewelry/precious metals)"
    )
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
    ], string='Purity/Karat', help="For jewelry items")

    # Valuation
    appraised_value = fields.Monetary(
        string='Appraised Value',
        required=True,
        currency_field='currency_id',
        help="Estimated market value"
    )
    loan_amount = fields.Monetary(
        string='Loan Amount',
        currency_field='currency_id',
        help="Loan amount for this specific item (if calculating per-item)"
    )

    # Related Fields
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='ticket_id.currency_id',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='ticket_id.company_id',
        readonly=True,
        store=True,
    )
    branch_id = fields.Many2one(
        'pawn.branch',
        string='Branch',
        related='ticket_id.branch_id',
        readonly=True,
        store=True,
    )
    state = fields.Selection(
        string='Status',
        related='ticket_id.state',
        readonly=True,
        store=True,
    )

    # Photos
    photo_1 = fields.Binary(
        string='Photo 1',
        attachment=True,
        help="Main photo of item"
    )
    photo_2 = fields.Binary(
        string='Photo 2',
        attachment=True,
        help="Additional photo"
    )
    photo_3 = fields.Binary(
        string='Photo 3',
        attachment=True,
        help="Additional photo"
    )
    photo_4 = fields.Binary(
        string='Photo 4',
        attachment=True,
        help="Additional photo"
    )

    # Barcode/Tracking
    barcode = fields.Char(
        string='Barcode',
        copy=False,
        help="Barcode for tracking item in custody"
    )

    # Inventory Link
    stock_move_ids = fields.One2many(
        'stock.move',
        'pawn_line_id',
        string='Stock Moves',
        readonly=True,
        help="Inventory movements for this item"
    )

    # Appraisal Info
    appraised_by = fields.Many2one(
        'res.users',
        string='Appraised By',
        help="User who appraised this item"
    )
    appraisal_date = fields.Date(
        string='Appraisal Date',
        default=fields.Date.context_today,
        help="Date of appraisal"
    )
    appraisal_notes = fields.Text(
        string='Appraisal Notes',
        help="Notes from appraiser"
    )

    # ============================================================
    # CONSTRAINTS
    # ============================================================

    @api.constrains('appraised_value')
    def _check_appraised_value(self):
        """Ensure appraised value is positive"""
        for record in self:
            if record.appraised_value <= 0:
                raise ValidationError(_('Appraised value must be greater than zero.'))

    @api.constrains('weight')
    def _check_weight(self):
        """Ensure weight is positive if specified"""
        for record in self:
            if record.weight and record.weight < 0:
                raise ValidationError(_('Weight cannot be negative.'))

    # ============================================================
    # ONCHANGE METHODS
    # ============================================================

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-fill fields from product template"""
        if self.product_id:
            self.name = self.product_id.name
            if self.product_id.categ_id:
                # Try to find matching pawn category
                pawn_category = self.env['pawn.item.category'].search([
                    ('name', '=ilike', self.product_id.categ_id.name)
                ], limit=1)
                if pawn_category:
                    self.category_id = pawn_category

    @api.onchange('category_id')
    def _onchange_category_id(self):
        """Suggest default description based on category"""
        if self.category_id and not self.name:
            self.name = f"{self.category_id.name} item"

    # ============================================================
    # COMPUTE METHODS
    # ============================================================

    @api.depends('name', 'brand', 'model')
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            name_parts = [record.name]
            if record.brand:
                name_parts.append(f"({record.brand}")
                if record.model:
                    name_parts[-1] += f" {record.model})"
                else:
                    name_parts[-1] += ")"
            elif record.model:
                name_parts.append(f"({record.model})")

            result.append((record.id, " ".join(name_parts)))
        return result

    # ============================================================
    # BUSINESS METHODS
    # ============================================================

    def _create_stock_move(self):
        """
        Create stock move when item is pledged (intake to custody).
        Phase 3: Inventory Integration - Enhanced implementation.
        """
        self.ensure_one()

        # Validate state
        if self.state not in ('draft', 'pledged'):
            raise ValidationError(_('Cannot create stock move for item in state: %s') % self.state)

        # Get stock locations from data file
        try:
            location_customer = self.env.ref('stock.stock_location_customers')
            location_custody = self.env.ref('pawnshop.stock_location_pawn_custody')
        except ValueError as e:
            raise UserError(_('Stock locations not properly configured. Please contact administrator.'))

        # Create product if not exists (for tracking this specific item)
        if not self.product_id:
            # Create a unique product for this pawned item
            product_name = f"{self.name}"
            if self.brand:
                product_name += f" - {self.brand}"
            if self.serial_number:
                product_name += f" (SN: {self.serial_number})"
            
            # Use pawned items category for storable products
            try:
                default_categ = self.env.ref('pawnshop.product_category_pawned_items')
            except ValueError:
                # Fallback to default product category
                default_categ = self.env.ref('product.product_category_all')
            
            product_vals = {
                'name': product_name,
                'type': 'product',  # Storable product
                'categ_id': default_categ.id,
                'sale_ok': False,
                'purchase_ok': False,
                'tracking': 'none',
                'default_code': self.barcode or False,
            }
            self.product_id = self.env['product.product'].create(product_vals)

        # Check if stock move already exists for this line
        existing_moves = self.stock_move_ids.filtered(
            lambda m: m.location_dest_id == location_custody and m.state == 'done'
        )
        if existing_moves:
            # Stock move already created, skip
            return existing_moves[0]

        # Create stock move (Virtual Customer Location → Pawn Custody)
        move_vals = {
            'name': f"Pledge: {self.name} [{self.ticket_id.ticket_no}]",
            'product_id': self.product_id.id,
            'product_uom_qty': 1,
            'product_uom': self.product_id.uom_id.id,
            'location_id': location_customer.id,
            'location_dest_id': location_custody.id,
            'pawn_line_id': self.id,
            'origin': self.ticket_id.ticket_no,
            'company_id': self.company_id.id,
        }

        move = self.env['stock.move'].create(move_vals)
        move._action_confirm()
        move._action_done()

        return move

    def _forfeit_item(self):
        """
        Move item from custody to forfeited inventory when ticket is forfeited.
        Phase 3: Inventory Integration - Enhanced implementation.
        """
        self.ensure_one()

        # Validate state
        if self.state != 'forfeited':
            raise ValidationError(_('Cannot forfeit item that is not in forfeited state.'))

        if not self.product_id:
            raise UserError(_('No product associated with this item. Cannot create stock move.'))

        # Get stock locations
        try:
            location_custody = self.env.ref('pawnshop.stock_location_pawn_custody')
            location_forfeited = self.env.ref('pawnshop.stock_location_pawn_forfeited')
        except ValueError:
            raise UserError(_('Stock locations not properly configured. Please contact administrator.'))

        # Check if already forfeited
        existing_moves = self.stock_move_ids.filtered(
            lambda m: m.location_dest_id == location_forfeited and m.state == 'done'
        )
        if existing_moves:
            # Already forfeited, skip
            return existing_moves[0]

        # Create stock move (Pawn Custody → Forfeited Inventory)
        move_vals = {
            'name': f"Forfeit: {self.name} [{self.ticket_id.ticket_no}]",
            'product_id': self.product_id.id,
            'product_uom_qty': 1,
            'product_uom': self.product_id.uom_id.id,
            'location_id': location_custody.id,
            'location_dest_id': location_forfeited.id,
            'pawn_line_id': self.id,
            'origin': self.ticket_id.ticket_no,
            'company_id': self.company_id.id,
        }

        move = self.env['stock.move'].create(move_vals)
        move._action_confirm()
        move._action_done()

        return move

    def _redeem_item(self):
        """
        Move item from custody back to customer when ticket is redeemed.
        Phase 3: Inventory Integration - Enhanced implementation.
        """
        self.ensure_one()

        # Validate state
        if self.state != 'redeemed':
            raise ValidationError(_('Cannot redeem item that is not in redeemed state.'))

        if not self.product_id:
            raise UserError(_('No product associated with this item. Cannot create stock move.'))

        # Get stock locations
        try:
            location_custody = self.env.ref('pawnshop.stock_location_pawn_custody')
            location_customer = self.env.ref('stock.stock_location_customers')
        except ValueError:
            raise UserError(_('Stock locations not properly configured. Please contact administrator.'))

        # Check if already redeemed
        existing_moves = self.stock_move_ids.filtered(
            lambda m: m.location_dest_id == location_customer and m.state == 'done'
        )
        if existing_moves:
            # Already redeemed, skip
            return existing_moves[0]

        # Create stock move (Pawn Custody → Customer)
        move_vals = {
            'name': f"Redeem: {self.name} [{self.ticket_id.ticket_no}]",
            'product_id': self.product_id.id,
            'product_uom_qty': 1,
            'product_uom': self.product_id.uom_id.id,
            'location_id': location_custody.id,
            'location_dest_id': location_customer.id,
            'pawn_line_id': self.id,
            'origin': self.ticket_id.ticket_no,
            'company_id': self.company_id.id,
        }

        move = self.env['stock.move'].create(move_vals)
        move._action_confirm()
        move._action_done()

        return move
