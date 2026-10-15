
from odoo import fields, models

class StockMove(models.Model):
    _inherit = 'stock.move'
    approval_line_id = fields.Many2one('approval.product.line', string='Línea de Requisición', index=True, copy=False)

class StockPicking(models.Model):
    _inherit = 'stock.picking'
    approval_request_ids = fields.Many2many('approval.request', string='Requerimientos', copy=False)
