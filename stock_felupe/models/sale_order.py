from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    picking_preparation_state = fields.Selection(
        [
            ('in_preparation', 'En Proceso de Alistamiento'),
            ('prepared', 'Alistado'),
        ],
        compute='_compute_picking_preparation_state',
        string='Estado de Alistamiento',
        tracking=True,
        store=True,
    )
    outgoing_picking_ids = fields.Many2many(
        'stock.picking',
        string='Entregas',
        compute='_compute_outgoing_pickings',
        store=True,
    )
    sale_margin = fields.Boolean(string='Aprobar Ventas', tracking=True)
    sale_margin_edit = fields.Boolean(
        string='Puede aprobar margen',
        compute='_compute_sale_margin_edit',
    )

    @api.depends('picking_ids', 'picking_ids.picking_type_code')
    def _compute_outgoing_pickings(self):
        for order in self:
            order.outgoing_picking_ids = order.picking_ids.filtered(
                lambda picking: picking.picking_type_code == 'outgoing'
            )

    @api.depends(
        'picking_ids',
        'picking_ids.picking_type_code',
        'picking_ids.state',
    )
    def _compute_picking_preparation_state(self):
        for order in self:
            pickings = order.picking_ids.filtered(
                lambda picking: picking.picking_type_code == 'internal'
            )
            if not pickings:
                order.picking_preparation_state = False
            elif any(
                picking.picking_preparation_state == 'in_preparation'
                for picking in pickings
            ):
                order.picking_preparation_state = 'in_preparation'
            elif all(
                picking.picking_preparation_state == 'prepared'
                for picking in pickings
            ):
                order.picking_preparation_state = 'prepared'
            else:
                order.picking_preparation_state = False

    @api.depends('company_id.res_users_sale_activity')
    @api.depends_context('uid')
    def _compute_sale_margin_edit(self):
        current_user = self.env.user
        for order in self:
            order.sale_margin_edit = (
                current_user in order.company_id.res_users_sale_activity
            )

    def action_open_margin_warning(self):
        self.ensure_one()
        return {
            'name': 'Advertencia de Margen',
            'type': 'ir.actions.act_window',
            'res_model': 'margin.warning.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_message': (
                    'Aprobar solicitud de cotizacion con margen inferior '
                    'a lo permitido.'
                ),
                'default_res_users_sale_activity': [
                    (6, 0, self.company_id.res_users_sale_activity.ids)
                ],
            },
        }
