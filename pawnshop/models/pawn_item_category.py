# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PawnItemCategory(models.Model):
    """
    Categories for pawned items (Jewelry, Gadgets, Tools, etc.)
    Used for rate determination, reporting, and inventory management
    """
    _name = 'pawn.item.category'
    _description = 'Pawn Item Category'
    _order = 'sequence, name'
    _parent_name = 'parent_id'
    _parent_store = True

    # Basic Information
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=False,
        help="Name of the category (e.g., 'Gold Jewelry', 'Electronics')"
    )
    code = fields.Char(
        string='Category Code',
        required=True,
        size=10,
        help="Short code for internal reference (e.g., 'GOLD', 'ELEC')"
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Order of display in lists"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Inactive categories cannot be used for new items"
    )

    # Hierarchy
    parent_id = fields.Many2one(
        'pawn.item.category',
        string='Parent Category',
        ondelete='cascade',
        help="Parent category for hierarchical structure"
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        'pawn.item.category',
        'parent_id',
        string='Child Categories'
    )

    # Description
    description = fields.Text(
        string='Description',
        help="Detailed description of items in this category"
    )
    color = fields.Integer(
        string='Color Index',
        help="Color for display in kanban view"
    )

    # Settings
    default_loan_to_value_ratio = fields.Float(
        string='Default LTV Ratio (%)',
        default=70.0,
        help="Default loan-to-value ratio for items in this category (e.g., 70 means 70% of appraised value)"
    )
    requires_serial = fields.Boolean(
        string='Requires Serial Number',
        default=False,
        help="If checked, items in this category must have a serial number"
    )
    requires_photo = fields.Boolean(
        string='Requires Photo',
        default=True,
        help="If checked, items in this category must have photos"
    )

    # Product Template for Forfeited Items
    product_categ_id = fields.Many2one(
        'product.category',
        string='Product Category',
        help="Default product category when items are forfeited and converted to saleable products"
    )

    # Statistics
    item_count = fields.Integer(
        string='Item Count',
        compute='_compute_item_count',
        help="Number of items currently in this category"
    )

    # SQL Constraints
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Category code must be unique!'),
        ('name_unique', 'UNIQUE(name)', 'Category name must be unique!'),
        ('ltv_ratio_check', 'CHECK(default_loan_to_value_ratio >= 0 AND default_loan_to_value_ratio <= 100)',
         'LTV ratio must be between 0 and 100!'),
    ]

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        """Prevent circular references in category hierarchy"""
        if self._has_cycle():
            raise ValidationError(_('You cannot create recursive categories.'))

    @api.constrains('code')
    def _check_code_format(self):
        """Ensure category code is uppercase alphanumeric"""
        for record in self:
            if record.code and not record.code.replace('-', '').replace('_', '').isalnum():
                raise ValidationError(_('Category code must contain only letters, numbers, hyphens, or underscores.'))

    def _compute_item_count(self):
        """Compute number of items in this category"""
        # Placeholder - will be implemented when pawn.ticket.line model is created
        for record in self:
            record.item_count = 0

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        """Allow searching by code or name"""
        if domain is None:
            domain = []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    def name_get(self):
        """Display as [CODE] Name or with parent path"""
        result = []
        for record in self:
            if record.parent_id:
                name = f"{record.parent_id.name} / {record.name}"
            else:
                name = f"[{record.code}] {record.name}"
            result.append((record.id, name))
        return result

    def action_view_items(self):
        """View all items in this category"""
        # Placeholder - will be implemented in Phase 2 when pawn.ticket.line model is created
        return {
            'type': 'ir.actions.act_window',
            'name': 'Items',
            'res_model': 'pawn.ticket.line',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id}
        }
