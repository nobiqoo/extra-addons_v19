# -*- coding: utf-8 -*-
from odoo import fields, models, _


class InvoiceCwLog(models.Model):
    _name = 'invoice.cw.log'
    _description = 'Log envíos a CargoWise'

    name = fields.Char('Nombre')
    move_id = fields.Many2one('account.move', 'Factura', ondelete='cascade')
    request_fname = fields.Char('Nombre Request', default='request.xml')
    request = fields.Binary('Request')
    response_fname = fields.Char('Nombre Response', default='response.xml')
    response = fields.Binary('Response')
    response_txt = fields.Text('Respuesta texto')
    type_doc = fields.Selection(
        selection=[
            ('invoiced', 'Facturado'),
            ('paid', 'Pagado'),
            ('cancelled', 'Cancelado'),
        ],
        string='Tipo de envío',
    )
    state = fields.Selection(
        selection=[
            ('done', 'Hecho'),
            ('error', 'Error'),
        ],
        string='Estado',
    )
    code_cw = fields.Char('Código CW')
    ref_inv_cw_id = fields.Many2one('invoice.reference.cw', 'Factura referencia CW')
