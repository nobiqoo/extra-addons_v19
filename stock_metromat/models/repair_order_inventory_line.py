from odoo import api, fields, models


class RepairOrderInventoryLine(models.Model):
    _name = 'repair.order.inventory.line'
    _description = 'Inventario de la orden de trabajo'
    _order = 'sequence, id'

    repair_id = fields.Many2one(
        comodel_name='repair.order',
        string='Orden de trabajo',
        required=True,
        index=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )
    item = fields.Integer(
        string='Ítem',
        compute='_compute_item',
    )
    quantity = fields.Integer(
        string='Cant',
        default=1,
        required=True,
    )
    description = fields.Char(
        string='Descripción',
        required=True,
    )
    serial = fields.Char(
        string='Serial',
    )
    reception_comment = fields.Char(
        string='Comentario de ingreso',
    )
    delivery_comment = fields.Char(
        string='Comentario de salida',
    )

    @api.depends('repair_id.inventory_line_ids', 'sequence')
    def _compute_item(self):
        for line in self:
            lines = line.repair_id.inventory_line_ids
            line.item = list(lines).index(line) + 1 if line in lines else 0
