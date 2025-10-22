# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PawnRedeemWizard(models.TransientModel):
    _name = 'pawn.redeem.wizard'
    _description = 'Redeem Pawn Ticket'

    ticket_id = fields.Many2one('pawn.ticket', string='Pawn Ticket', required=True)
    principal_amount = fields.Monetary(string='Principal', currency_field='currency_id')
    interest_amount = fields.Monetary(string='Interest', currency_field='currency_id')
    penalty_amount = fields.Monetary(string='Penalty', currency_field='currency_id')
    service_fee = fields.Monetary(string='Service Fee', currency_field='currency_id')
    total_due = fields.Monetary(string='Total Due', currency_field='currency_id', compute='_compute_total_due')

    payment_method = fields.Selection(
        [('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('gcash', 'GCash'), ('maya', 'Maya'), ('other', 'Other')],
        string='Payment Method'
    )
    payment_ref = fields.Char(string='Payment Reference')

    currency_id = fields.Many2one('res.currency', related='ticket_id.currency_id', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ticket = self.env['pawn.ticket'].browse(self.env.context.get('active_id'))
        if ticket:
            res.setdefault('ticket_id', ticket.id)
            res.setdefault('principal_amount', ticket.principal_amount or 0.0)
            res.setdefault('interest_amount', ticket.interest_amount or 0.0)
            res.setdefault('penalty_amount', ticket.penalty_amount or 0.0)
            res.setdefault('service_fee', ticket.service_fee or 0.0)
        return res

    @api.depends('principal_amount', 'interest_amount', 'penalty_amount', 'service_fee')
    def _compute_total_due(self):
        for wiz in self:
            wiz.total_due = (wiz.principal_amount or 0.0) + (wiz.interest_amount or 0.0) + (wiz.penalty_amount or 0.0) + (wiz.service_fee or 0.0)

    def action_confirm(self):
        self.ensure_one()
        ticket = self.ticket_id
        if ticket.state not in ('pledged', 'renewed'):
            raise UserError(_('Only active tickets can be redeemed.'))

        # Build redemption invoice using provided amounts
        vals = ticket._prepare_invoice_vals('redemption')
        lines = []
        # Principal
        principal_product_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.service_fee_product_id') or 0)
        if not principal_product_id:
            # fallback to interest product if service not set
            principal_product_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.interest_product_id') or 0)
        if not principal_product_id:
            raise UserError(_('Configure at least one service product in settings to invoice principal.'))
        lines.append((0, 0, {
            'product_id': principal_product_id,
            'name': _('Principal for %s') % (ticket.ticket_no,),
            'quantity': 1,
            'price_unit': self.principal_amount or 0.0,
        }))
        # Interest
        if self.interest_amount:
            prod_interest_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.interest_product_id') or 0)
            if not prod_interest_id:
                raise UserError(_('Configure Interest Income Product in settings.'))
            lines.append((0, 0, {'product_id': prod_interest_id, 'name': _('Interest for %s') % ticket.ticket_no, 'quantity': 1, 'price_unit': self.interest_amount}))
        # Penalty
        if self.penalty_amount:
            prod_penalty_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.penalty_product_id') or 0)
            if not prod_penalty_id:
                raise UserError(_('Configure Penalty Product in settings.'))
            lines.append((0, 0, {'product_id': prod_penalty_id, 'name': _('Penalty for %s') % ticket.ticket_no, 'quantity': 1, 'price_unit': self.penalty_amount}))
        # Service
        if self.service_fee:
            prod_service_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.service_fee_product_id') or 0)
            if not prod_service_id:
                raise UserError(_('Configure Service Fee Product in settings.'))
            lines.append((0, 0, {'product_id': prod_service_id, 'name': _('Service Fee for %s') % ticket.ticket_no, 'quantity': 1, 'price_unit': self.service_fee}))

        vals['invoice_line_ids'] = lines
        # mirror payment notes on invoice
        vals.update({'x_payment_method': self.payment_method, 'x_payment_ref': self.payment_ref})
        inv = self.env['account.move'].create(vals)

        # Auto-post invoice
        try:
            inv.action_post()
        except Exception as e:
            # keep going but surface minimal info
            raise UserError(_('Failed to post invoice: %s') % (e,))

        # Set ticket to redeemed before moving items (line._redeem_item checks state)
        ticket.write({'state': 'redeemed', 'date_redeemed': fields.Date.context_today(self)})
        # Move each line out of custody
        for line in ticket.line_ids:
            line._redeem_item()

        # Register payment for full residual using the given payment hints
        try:
            pay_reg = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=inv.ids).create({
                'payment_date': fields.Date.context_today(self),
                'amount': inv.amount_residual,
                'communication': _('Redemption for %s') % (ticket.ticket_no,),
            })
            pay_reg.action_create_payments()
        except Exception as e:
            # If payment registration fails, still proceed; the invoice remains posted and unpaid
            pass

        # Link invoice
        ticket.invoice_ids = [(4, inv.id)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Redemption Invoice'),
            'res_model': 'account.move',
            'res_id': inv.id,
            'view_mode': 'form',
            'target': 'current',
        }
