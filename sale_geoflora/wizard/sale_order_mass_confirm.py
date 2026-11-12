# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrderMassConfirm(models.TransientModel):
    _name = 'sale.order.mass.confirm'
    _description = 'Mass quotation confirmation result'

    confirmed_order_ids = fields.Many2many(
        'sale.order',
        relation='sale_order_mass_confirm_rel',
        string='Confirmed Orders',
    )
    confirmed_count = fields.Integer(string='Confirmed', compute='_compute_counts')
    skipped_count = fields.Integer(string='Skipped', compute='_compute_counts')
    line_ids = fields.One2many(
        'sale.order.mass.confirm.line', 'wizard_id',
        string='Skipped Orders',
    )

    @api.depends('confirmed_order_ids', 'line_ids')
    def _compute_counts(self):
        """Totales de órdenes confirmadas y omitidas."""
        for wizard in self:
            wizard.confirmed_count = len(wizard.confirmed_order_ids)
            wizard.skipped_count = len(wizard.line_ids)


class SaleOrderMassConfirmLine(models.TransientModel):
    _name = 'sale.order.mass.confirm.line'
    _description = 'Quotation skipped in mass confirmation'

    wizard_id = fields.Many2one('sale.order.mass.confirm', required=True, ondelete='cascade')
    order_id = fields.Many2one('sale.order', string='Order', readonly=True)
    partner_id = fields.Many2one(related='order_id.partner_id')
    state = fields.Selection(related='order_id.state')
    reason = fields.Text(string='Reason', readonly=True)
