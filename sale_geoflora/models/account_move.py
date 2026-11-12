# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools import format_date

WEBFLOR_MOVE_FIELDS = [
    'webflor_order_number',
    'webflor_invoice_number',
    'webflor_sale_type',
    'webflor_negotiation_term',
    'webflor_order_type',
    'webflor_freight_forwarder',
    'webflor_airline',
    'webflor_delivery_date',
    'webflor_dispatch_date',
    'webflor_mawb_number',
    'webflor_hawb_number',
    'webflor_grandchild_guide_number',
]


def _webflor_field(string, compute='_compute_webflor_info', **kwargs):
    return fields.Char(
        string=string,
        compute=compute,
        store=True,
        readonly=False,
        copy=True,
        **kwargs,
    )


class AccountMove(models.Model):
    _inherit = 'account.move'

    webflor_order_number = _webflor_field('WebFlor Order No.')
    webflor_invoice_number = _webflor_field(
        'WebFlor Invoice No.', compute='_compute_webflor_invoice_number', index='btree_not_null')
    webflor_sale_type = _webflor_field('Sale Type')
    webflor_negotiation_term = _webflor_field('Negotiation Term')
    webflor_order_type = _webflor_field('Order Type')
    webflor_freight_forwarder = _webflor_field('Freight Forwarder')
    webflor_airline = _webflor_field('Airline')
    webflor_delivery_date = _webflor_field('WebFlor Delivery Date')
    webflor_dispatch_date = _webflor_field('WebFlor Dispatch Date')
    webflor_mawb_number = _webflor_field('Master Air Waybill (MAWB)')
    webflor_hawb_number = _webflor_field('House Air Waybill (HAWB)')
    webflor_grandchild_guide_number = _webflor_field('Sub-house Air Waybill')

    @api.depends(
        'invoice_line_ids.sale_line_ids',
        *[f'invoice_line_ids.sale_line_ids.order_id.{fname}' for fname in WEBFLOR_MOVE_FIELDS
          if fname != 'webflor_invoice_number'],
    )
    def _compute_webflor_info(self):
        """Hereda la información WebFlor de las órdenes de venta mientras la factura está en borrador."""
        self._set_webflor_values([fname for fname in WEBFLOR_MOVE_FIELDS if fname != 'webflor_invoice_number'])

    @api.depends('invoice_line_ids.sale_line_ids', 'invoice_line_ids.sale_line_ids.order_id.webflor_invoice_number')
    def _compute_webflor_invoice_number(self):
        """Hereda el N° Invoice WebFlor de las órdenes de venta mientras la factura está en borrador."""
        self._set_webflor_values(['webflor_invoice_number'])

    def _set_webflor_values(self, field_names):
        """Copia los campos WebFlor de las órdenes origen; con varias órdenes concatena los valores distintos."""
        for move in self:
            if move.state != 'draft':
                continue
            orders = move.invoice_line_ids.sale_line_ids.order_id.sorted('name')
            for fname in field_names:
                if not orders:
                    move[fname] = move[fname]
                    continue
                values = []
                for order in orders:
                    value = order[fname]
                    if value and hasattr(value, 'strftime'):
                        value = format_date(self.env, value)
                    if value and value not in values:
                        values.append(value)
                move[fname] = ', '.join(values) or False

    def _get_webflor_receivable_label(self):
        """Texto WebFlor que se agrega a la etiqueta de la cuenta por cobrar."""
        self.ensure_one()
        return f'(N°{self.webflor_invoice_number} WF)' if self.webflor_invoice_number else ''
