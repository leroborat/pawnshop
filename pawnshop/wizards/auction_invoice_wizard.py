# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PawnAuctionInvoiceWizard(models.TransientModel):
    _name = 'pawn.auction.invoice.wizard'
    _description = 'Create Auction Invoice for Forfeited Item'

    line_id = fields.Many2one(
        'pawn.ticket.line',
        string='Pawned Item',
        required=True,
    )
    ticket_id = fields.Many2one(
        'pawn.ticket',
        string='Pawn Ticket',
        related='line_id.ticket_id',
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Buyer',
        required=True,
        domain=[('type', '!=', 'private')],
        help='Auction buyer/customer'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='ticket_id.currency_id',
        readonly=True,
    )
    price_unit = fields.Monetary(
        string='Price',
        currency_field='currency_id',
        help='Sale price for this forfeited item'
    )
    add_service_fee = fields.Boolean(string='Add Service Fee', default=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line = self.env['pawn.ticket.line'].browse(self.env.context.get('default_line_id'))
        if line:
            res.setdefault('line_id', line.id)
            res.setdefault('price_unit', line.appraised_value or 0.0)
            # Pre-fill default buyer from settings if present
            auction_customer_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.auction_customer_id') or 0)
            if auction_customer_id:
                res.setdefault('partner_id', auction_customer_id)
        return res

    def action_confirm(self):
        self.ensure_one()
        line = self.line_id
        if line.state != 'forfeited':
            raise UserError(_('Only forfeited items can be auction invoiced.'))
        if not line.product_id:
            raise UserError(_('This item does not have a product associated.'))
        if self.price_unit is None:
            raise UserError(_('Please set a price.'))

        # Build invoice
        move_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': line.ticket_id.ticket_no,
            'currency_id': line.ticket_id.currency_id.id,
            'pawn_ticket_id': line.ticket_id.id,
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'name': _('%s (Ticket %s)') % (line.name, line.ticket_id.ticket_no),
                    'quantity': 1,
                    'price_unit': self.price_unit,
                })
            ],
        }

        # Optional: add service fee line if toggled and configured
        if self.add_service_fee:
            service_product_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.service_fee_product_id') or 0)
            if service_product_id:
                move_vals['invoice_line_ids'].append((0, 0, {
                    'product_id': service_product_id,
                    'name': _('Auction Service Fee'),
                    'quantity': 1,
                    'price_unit': 0.0,
                }))

        inv = self.env['account.move'].create(move_vals)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Auction Invoice'),
            'res_model': 'account.move',
            'res_id': inv.id,
            'view_mode': 'form',
            'target': 'current',
        }
