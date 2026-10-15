# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class PurchaseServiceAcceptanceLine(models.Model):
    _name = 'purchase.service.acceptance.line'
    _description = 'Purchase Service Acceptance Line'

    acceptance_id = fields.Many2one(
        comodel_name='purchase.service.acceptance',
        string='Service Acceptance',
        required=True,
        ondelete='cascade',
    )
    purchase_order_id = fields.Many2one(
        related='acceptance_id.purchase_order_id',
        store=True,
    )
    purchase_line_id = fields.Many2one(
        comodel_name='purchase.order.line',
        string='Purchase Order Line',
        required=True,
        ondelete='cascade',
        domain="[('order_id', '=', purchase_order_id), ('product_id.type', '=', 'service')]",
    )
    product_id = fields.Many2one(related='purchase_line_id.product_id', store=True, readonly=True)
    description = fields.Text(related='purchase_line_id.name', string='Description', readonly=True)
    analytic_distribution = fields.Json(related='purchase_line_id.analytic_distribution', readonly=True)
    analytic_precision = fields.Integer(
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic'),
    )
    company_id = fields.Many2one(related='purchase_line_id.company_id', store=True, readonly=True)
    product_uom_id = fields.Many2one(
        related='purchase_line_id.product_uom_id', string='Unit of Measure', readonly=True,
    )
    product_qty_ordered = fields.Float(
        related='purchase_line_id.product_qty', string='Ordered Qty', readonly=True,
    )
    price_unit = fields.Float(related='purchase_line_id.price_unit', readonly=True)
    taxes_id = fields.Many2many(
        comodel_name='account.tax',
        related='purchase_line_id.tax_ids',
        string='Taxes',
        readonly=True,
    )
    qty_previously_accepted = fields.Float(
        string='Previously Accepted Qty',
        compute='_compute_qty_previously_accepted',
    )
    qty_pending = fields.Float(
        string='Pending Qty',
        compute='_compute_qty_pending',
    )
    qty_accepted = fields.Float(string='Accepted Qty')
    price_tax = fields.Monetary(
        string='Taxes',
        compute='_compute_amounts',
        currency_field='currency_id',
    )
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_amounts',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(related='purchase_line_id.currency_id')
    state = fields.Selection(related='acceptance_id.state', string='Acceptance Status', store=True)

    @api.depends('purchase_line_id')
    def _compute_qty_previously_accepted(self):
        for line in self:
            if line.purchase_line_id:
                line.qty_previously_accepted = line.purchase_line_id._get_service_acceptance_qty_accepted(
                    exclude_line=line
                )
            else:
                line.qty_previously_accepted = 0.0

    @api.depends('product_qty_ordered', 'qty_previously_accepted')
    def _compute_qty_pending(self):
        for line in self:
            line.qty_pending = max(line.product_qty_ordered - line.qty_previously_accepted, 0.0)

    @api.depends('qty_accepted', 'price_unit', 'taxes_id')
    def _compute_amounts(self):
        for line in self:
            base_amount = line.qty_accepted * line.price_unit
            if line.taxes_id:
                taxes_res = line.taxes_id.compute_all(
                    line.price_unit,
                    currency=line.currency_id,
                    quantity=line.qty_accepted,
                    product=line.product_id,
                    partner=line.purchase_order_id.partner_id,
                )
                tax_amount = taxes_res['total_included'] - taxes_res['total_excluded']
            else:
                tax_amount = 0.0
            line.price_tax = tax_amount
            line.subtotal = base_amount + tax_amount

    @api.constrains('qty_accepted')
    def _check_qty_accepted(self):
        if self.env.context.get('skip_qty_accepted_check'):
            return
        prec = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if float_compare(line.qty_accepted, 0.0, precision_digits=prec) <= 0:
                raise ValidationError(_('The accepted quantity must be greater than zero.'))
            if float_compare(line.qty_accepted, line.qty_pending, precision_digits=prec) > 0:
                raise ValidationError(_('The accepted quantity cannot be higher than the pending quantity.'))
