# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PawnRenewWizard(models.TransientModel):
    _name = 'pawn.renew.wizard'
    _description = 'Renew Pawn Ticket'

    ticket_id = fields.Many2one('pawn.ticket', string='Pawn Ticket', required=True)
    new_maturity_date = fields.Date(string='New Maturity Date', required=True)
    interest_amount = fields.Monetary(string='Interest', currency_field='currency_id')
    penalty_amount = fields.Monetary(string='Penalty', currency_field='currency_id')
    service_fee = fields.Monetary(string='Service Fee', currency_field='currency_id')
    total_due = fields.Monetary(string='Total Due', currency_field='currency_id', compute='_compute_total_due')

    currency_id = fields.Many2one('res.currency', related='ticket_id.currency_id', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ticket = self.env['pawn.ticket'].browse(self.env.context.get('active_id'))
        if ticket:
            res.setdefault('ticket_id', ticket.id)
            # Prefill using ticket computed amounts
            res.setdefault('interest_amount', ticket.interest_amount or 0.0)
            res.setdefault('penalty_amount', ticket.penalty_amount or 0.0)
            res.setdefault('service_fee', ticket.service_fee or 0.0)
            # Default extension based on company setting
            days = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.default_maturity_days', '30'))
            res.setdefault('new_maturity_date', fields.Date.add(ticket.date_maturity or fields.Date.context_today(self), days=days))
        return res

    @api.depends('interest_amount', 'penalty_amount', 'service_fee')
    def _compute_total_due(self):
        for wiz in self:
            wiz.total_due = (wiz.interest_amount or 0.0) + (wiz.penalty_amount or 0.0) + (wiz.service_fee or 0.0)

    def action_confirm(self):
        self.ensure_one()
        ticket = self.ticket_id
        if ticket.state not in ('pledged', 'renewed'):
            raise UserError(_('Only active tickets can be renewed.'))
        # Create renewal invoice via ticket helpers
        vals = ticket._prepare_invoice_vals('renewal')
        # Override lines with wizard values if provided
        lines = []
        if self.interest_amount:
            prod_interest_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.interest_product_id') or 0)
            if not prod_interest_id:
                raise UserError(_('Configure Interest Income Product in settings.'))
            lines.append((0, 0, {'product_id': prod_interest_id, 'name': _('Interest for %s') % ticket.ticket_no, 'quantity': 1, 'price_unit': self.interest_amount}))
        if self.penalty_amount:
            prod_penalty_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.penalty_product_id') or 0)
            if not prod_penalty_id:
                raise UserError(_('Configure Penalty Product in settings.'))
            lines.append((0, 0, {'product_id': prod_penalty_id, 'name': _('Penalty for %s') % ticket.ticket_no, 'quantity': 1, 'price_unit': self.penalty_amount}))
        if self.service_fee:
            prod_service_id = int(self.env['ir.config_parameter'].sudo().get_param('pawnshop.service_fee_product_id') or 0)
            if not prod_service_id:
                raise UserError(_('Configure Service Fee Product in settings.'))
            lines.append((0, 0, {'product_id': prod_service_id, 'name': _('Service Fee for %s') % ticket.ticket_no, 'quantity': 1, 'price_unit': self.service_fee}))
        vals['invoice_line_ids'] = lines
        inv = self.env['account.move'].create(vals)
        # Extend maturity date
        ticket.write({'date_maturity': self.new_maturity_date, 'state': 'renewed'})
        # Link invoice
        ticket.invoice_ids = [(4, inv.id)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Renewal Invoice'),
            'res_model': 'account.move',
            'res_id': inv.id,
            'view_mode': 'form',
            'target': 'current',
        }
