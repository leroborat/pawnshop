# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PawnBranch(models.Model):
    """
    Represents a physical pawnshop branch location.
    Each branch has its own warehouse for inventory management
    and generates unique ticket sequences.
    """
    _name = 'pawn.branch'
    _description = 'Pawnshop Branch'
    _order = 'sequence, name'
    
    # SQL Constraints (Odoo 19 syntax)
    _constraints = [
        models.Constraint('UNIQUE(code)', 'Branch code must be unique!'),
        models.Constraint('UNIQUE(name, company_id)', 'Branch name must be unique per company!'),
    ]
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Basic Information
    name = fields.Char(
        string='Branch Name',
        required=True,
        tracking=True,
        help="Full name of the branch (e.g., 'Manila Main Branch')"
    )
    code = fields.Char(
        string='Branch Code',
        required=True,
        size=5,
        tracking=True,
        help="Short code for branch identification (e.g., 'MNL01'). Used in ticket numbering."
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Order of display in lists and reports"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help="Inactive branches cannot process new transactions"
    )

    # Location Details
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one(
        'res.country.state',
        string='State'
    )
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one(
        'res.country',
        string='Country'
    )
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')

    # Operational Settings
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        required=True,
        ondelete='restrict',
        tracking=True,
        help="Warehouse for managing this branch's inventory (collateral, forfeited items)"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )

    # Ticket numbering (optional per-branch sequence)
    ticket_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Ticket Sequence',
        help="Optional per-branch ticket sequence. If not set, the global pawn.ticket sequence will be used."
    )

    # Manager
    manager_id = fields.Many2one(
        'res.users',
        string='Branch Manager',
        tracking=True,
        help="User responsible for this branch"
    )

    # Statistics (computed)
    ticket_count = fields.Integer(
        string='Active Tickets',
        compute='_compute_statistics',
        help="Number of active pawn tickets"
    )
    due_today_count = fields.Integer(
        string='Due Today',
        compute='_compute_statistics',
        help="Tickets maturing today"
    )
    overdue_count = fields.Integer(
        string='Overdue',
        compute='_compute_statistics',
        help="Tickets past grace period"
    )

    @api.constrains('code')
    def _check_code_format(self):
        """Ensure branch code is uppercase alphanumeric"""
        for record in self:
            if record.code and not record.code.replace('-', '').replace('_', '').isalnum():
                raise ValidationError(_('Branch code must contain only letters, numbers, hyphens, or underscores.'))

    def _compute_statistics(self):
        """Compute ticket statistics for each branch"""
        from datetime import date

        for record in self:
            tickets = self.env['pawn.ticket'].search([
                ('branch_id', '=', record.id),
                ('state', 'in', ('pledged', 'renewed'))
            ])

            record.ticket_count = len(tickets)
            record.due_today_count = len(tickets.filtered('is_due_today'))
            record.overdue_count = len(tickets.filtered(lambda t: t.is_overdue and not t.is_in_grace))

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        """Allow searching by code or name"""
        if domain is None:
            domain = []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)

    def name_get(self):
        """Display as [CODE] Name"""
        result = []
        for record in self:
            name = f"[{record.code}] {record.name}"
            result.append((record.id, name))
        return result

    def action_view_tickets(self):
        """View all tickets for this branch"""
        # Placeholder - will be implemented in Phase 2 when pawn.ticket model is created
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pawn Tickets',
            'res_model': 'pawn.ticket',
            'view_mode': 'list,form',
            'domain': [('branch_id', '=', self.id)],
            'context': {'default_branch_id': self.id}
        }

    def action_view_due_today(self):
        """View tickets due today for this branch"""
        # Placeholder - will be implemented in Phase 2
        today = fields.Date.context_today(self)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tickets Due Today',
            'res_model': 'pawn.ticket',
            'view_mode': 'list,form',
            'domain': [('branch_id', '=', self.id), ('maturity_date', '=', today)],
            'context': {'default_branch_id': self.id}
        }

    def action_view_overdue(self):
        """View overdue tickets for this branch"""
        # Placeholder - will be implemented in Phase 2
        today = fields.Date.context_today(self)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Overdue Tickets',
            'res_model': 'pawn.ticket',
            'view_mode': 'list,form',
            'domain': [('branch_id', '=', self.id), ('maturity_date', '<', today), ('state', 'in', ['pledged', 'grace'])],
            'context': {'default_branch_id': self.id}
        }

    def action_new_ticket(self):
        """Open intake wizard for creating new ticket"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Pawn Ticket',
            'res_model': 'pawn.intake.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_branch_id': self.id}
        }
