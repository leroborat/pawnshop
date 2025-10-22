# -*- coding: utf-8 -*-

from odoo import models, fields


class StockMove(models.Model):
    """
    Extend stock.move to link inventory movements with pawn ticket lines.
    """
    _inherit = 'stock.move'

    pawn_line_id = fields.Many2one(
        'pawn.ticket.line',
        string='Pawn Ticket Line',
        ondelete='restrict',
        index=True,
        help="Link to pawn ticket line for this inventory movement"
    )
    pawn_ticket_id = fields.Many2one(
        'pawn.ticket',
        string='Pawn Ticket',
        related='pawn_line_id.ticket_id',
        store=True,
        readonly=True,
        help="Related pawn ticket"
    )
