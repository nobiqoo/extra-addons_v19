from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    carrier_guide = fields.Char(string='Guia del Transportista')
    picking_preparation_state = fields.Selection(
        [
            ('in_preparation', 'En Proceso de Alistamiento'),
            ('prepared', 'Alistado'),
        ],
        compute='_compute_picking_preparation_state',
        string='Estado de Alistamiento',
        tracking=True,
    )
    delivery_carrier_id = fields.Many2one(
        'delivery.carrier.master',
        string='Empresa de Envio',
    )

    @api.depends('state')
    def _compute_picking_preparation_state(self):
        for picking in self:
            if picking.state == 'done':
                picking.picking_preparation_state = 'prepared'
            elif picking.state in ('assigned', 'confirmed'):
                picking.picking_preparation_state = 'in_preparation'
            else:
                picking.picking_preparation_state = False
