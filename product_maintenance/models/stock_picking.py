# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking' 

    def button_validate(self):
        for record in self:
            qualitys = self.env['quality.check'].search([
                ('picking_id', '=', record.id),
                ('test_type', '=', 'maintenance')])
            for quality in qualitys.filtered(
                    lambda x: not x.picking_id.return_id and x.repair_id.state != 'done'):
                moves = record.move_ids.filtered(
                    lambda x: x.product_id.id == quality.product_id.id)
                qty_to_done = sum([x.quantity for x in moves])
                if qty_to_done != 0:
                    raise ValidationError(
                        'No se puede validar la transferecia ya que la reparación {name} no está terminada.'.format(name=quality.repair_id.name))
        res = super().button_validate()
        for record in self.filtered(lambda x: not x.return_id and record.state == 'done' and x.picking_type_code == 'incoming'):
            order = self.env['purchase.order'].search([('name', '=', record.origin)])
            for move in record.move_ids:
                for line in move.move_line_ids.filtered(lambda x: x.product_id.is_maintenance_product and x.lot_id and not x.product_maintenance_id):
                    exist_product = self.env['product.maintenance'].search([
                        ('product_id', '=', move.product_id.id),
                        ('lot_id', '=', line.lot_id.id)
                    ])
                    if not exist_product:
                        product = self.env['product.maintenance'].create({
                            'product_id': move.product_id.id,
                            'provider_id': order.partner_id.id,
                            'name': '[' + line.lot_id.name  + '] ' + move.product_id.name,
                            'serial_no': line.lot_id.name,
                            'brand_id': move.product_id.product_brand_id.id,
                            'order_id': order.id if order else False,
                            'picking_id': record.id,
                            'stock_move_id': move.id,
                            'lot_id': line.lot_id.id,
                            'partner_id': move.product_id.partner_id.id
                        })
                        line.product_maintenance_id = product
        for record in self.filtered(lambda x: x.return_id and record.state == 'done'):
            for move in record.move_ids:
                for line in move.move_line_ids.filtered(
                        lambda x: x.product_id.is_maintenance_product and x.lot_id):
                    self.env['product.maintenance'].search([
                        ('product_id', '=', move.product_id.id),
                        ('lot_id', '=', line.lot_id.id),
                        ('picking_id', '=', record.return_id.id)
                    ]).unlink()
        return res