# -*- coding: utf-8 -*-
from odoo import fields, models


class InvoiceReferenceCW(models.Model):
    _name = 'invoice.reference.cw'
    _description = 'Reference to CW invoices'
    _rec_name = 'code_cw'

    code_cw = fields.Char('Code CW')
    city = fields.Char('City')
    customer_order = fields.Char('Customer Order')
    hbl = fields.Char('HBL')
    motor_ship = fields.Char('Motorship')
    position = fields.Char('Position')
    destination = fields.Char('Destination')
    text_weight = fields.Char('Weight')
    volume = fields.Char('Volume')
    salesman_cw_id = fields.Many2one('res.partner', 'Vendor')
    move_id = fields.Many2one('account.move', 'Document')
    cw_log_ids = fields.One2many('invoice.cw.log', 'ref_inv_cw_id', 'Log CW')

    def send_state_invoicing_to_cw(self):
        self.ensure_one()
        self.move_id.send_posted_invoice_to_cw(self.id)

    def send_state_paid_to_cw(self):
        self.ensure_one()
        self.move_id.send_posted_paid_to_cw(self.id)

    def send_state_cancelled_to_cw(self):
        self.ensure_one()
        self.move_id.send_posted_cancelled_to_cw(self.id)
