# -*- coding: utf-8 -*-

from odoo import models, fields


class ResUsers(models.Model):
    """
    Extend res.users to add branch assignment for multi-branch access control.
    """
    _inherit = 'res.users'

    branch_ids = fields.Many2many(
        'pawn.branch',
        'pawn_branch_user_rel',
        'user_id',
        'branch_id',
        string='Allowed Branches',
        help="Branches this user can access. Leave empty for managers/admins to access all branches."
    )
