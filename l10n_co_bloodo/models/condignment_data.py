# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ConsignmentData(models.Model):
    _name = 'consignment.data'
    _description = 'Remesa de transporte'

    move_line_id = fields.Many2one('account.move.line',
                            'línea de factura',
                            ondelete='cascade')
    rndc_id = fields.Char('Radicado remesa',
                            help='Número de radicado de aceptación remesa')
    consignment_id = fields.Char('Número remesa')
    freight = fields.Integer('Valor flete')
    quantity = fields.Integer('Cantidad transportada')
    udm = fields.Selection([('KGM', 'kg'),
                            ('GLL', 'gal')],
                            'UdM')
    order_ref = fields.Char('Orden de compra')
    transport_rec = fields.Selection([('0', 'Servicio adicional'),
                                      ('1', 'Remesa de transporte registrada en el RNDC')],
                            'Tipo servicio')
