# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    webflor_pending_order_ids = fields.Many2many(
        'sale.order',
        string='Pending orders of the same WebFlor Invoice',
        compute='_compute_webflor_pending_order_ids',
    )

    @api.depends('sale_order_ids')
    def _compute_webflor_pending_order_ids(self):
        """Órdenes del mismo N° Invoice WebFlor que no se seleccionaron y siguen por facturar."""
        for wizard in self:
            orders = wizard.sale_order_ids.filtered('webflor_invoice_number')
            if not orders:
                wizard.webflor_pending_order_ids = False
                continue
            wizard.webflor_pending_order_ids = self.env['sale.order'].search([
                ('webflor_invoice_number', 'in', orders.mapped('webflor_invoice_number')),
                ('company_id', 'in', orders.company_id.ids),
                ('id', 'not in', orders.ids),
                '|', ('state', 'in', ('draft', 'sent')), ('invoice_status', '=', 'to invoice'),
            ])
