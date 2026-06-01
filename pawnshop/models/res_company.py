# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    branch_code = fields.Char(
        string='Branch Code',
        size=5,
        tracking=True,
        help="Short code for branch identification (e.g., 'MNL01'). Used in ticket numbering."
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        ondelete='restrict',
        help="Warehouse for managing this branch's inventory"
    )
    ticket_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Ticket Sequence',
        help="Per-branch ticket sequence. If not set, the global pawn.ticket sequence will be used."
    )
    manager_id = fields.Many2one(
        'res.users',
        string='Branch Manager',
        help="User responsible for this branch"
    )

    is_pawn_branch = fields.Boolean(
        string='Is Pawn Branch',
        default=False,
        tracking=True,
        help="Check this if the company operates as a pawnshop branch"
    )

    @api.constrains('branch_code')
    def _check_branch_code_format(self):
        for record in self:
            if record.branch_code and not record.branch_code.replace('-', '').replace('_', '').isalnum():
                raise ValidationError(_('Branch code must contain only letters, numbers, hyphens, or underscores.'))

    def name_get(self):
        result = []
        for record in self:
            if record.parent_id and record.branch_code:
                name = f"[{record.branch_code}] {record.name}"
            else:
                name = record.name
            result.append((record.id, name))
        return result