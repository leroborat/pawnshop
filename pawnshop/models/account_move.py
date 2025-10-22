# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    pawn_ticket_id = fields.Many2one(
        'pawn.ticket',
        string='Pawn Ticket',
        ondelete='set null',
        index=True,
        help="Pawn ticket associated with this invoice"
    )

    # Simple payment annotations (Community scope)
    x_payment_method = fields.Selection(
        [
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('gcash', 'GCash'),
            ('maya', 'Maya'),
            ('other', 'Other'),
        ],
        string='Payment Method'
    )
    x_payment_ref = fields.Char(string='Payment Reference')
