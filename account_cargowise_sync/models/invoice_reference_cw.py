# -*- coding: utf-8 -*-
from odoo import fields, models


class InvoiceReferenceCW(models.Model):
    _name = 'invoice.reference.cw'
    _description = 'Referencia de facturas CW'
    _rec_name = 'code_cw'

    code_cw = fields.Char('Código CW')
    city = fields.Char('Ciudad')
    customer_order = fields.Char('Orden del cliente')
    hbl = fields.Char('HBL')
    motor_ship = fields.Char('Motonave')
    position = fields.Char('Posición')
    destination = fields.Char('Destino')
    text_weight = fields.Char('Peso')
    volume = fields.Char('Volumen')
    salesman_cw_id = fields.Many2one('res.partner', 'Vendedor')
    move_id = fields.Many2one('account.move', 'Documento', ondelete='cascade')
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
