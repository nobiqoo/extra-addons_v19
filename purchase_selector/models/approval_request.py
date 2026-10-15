from odoo import models, fields

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    request_status = fields.Selection(selection_add=[
        ('abastecido', 'Transferido internamente'),
    ])

    picking_ids = fields.Many2many(
        'stock.picking',
        'approval_request_picking_rel',
        'approval_request_id',
        'picking_id',
        string='Pickings de Abastecimiento',
        copy=False,
    )
    product_line_ids = fields.One2many(
        'approval.product.line', 'approval_request_id', string="Líneas de producto"
    )
