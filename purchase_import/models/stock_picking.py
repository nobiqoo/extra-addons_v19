# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_move_line_ids = fields.One2many(
        'stock.move.line',
        'picking_id',
        string='Línea de operación',
    )

    def button_validate(self):
        if not self.env.context.get('from_import'):
            for picking in self.filtered(lambda s: s.picking_type_code == 'incoming'):
                purchase_order = picking.purchase_id

                if purchase_order:
                    import_orders = self.env['purchase.import'].search([
                        ('purchases_ids', 'in', purchase_order.ids)
                    ])

                    if import_orders:
                        import_info = "\n".join([
                            f"- Orden(es) de Compra: {purchase_order.name} - Importación: {imp.name}"
                            for imp in import_orders
                        ])
                        error_message = _(
                            """No se puede validar la orden de compra, debido a que está relacionado con una importación. Por favor, realice la validación a partir de la importación: {}""").format(import_info)
                        raise UserError(error_message)
        res = super(StockPicking, self).button_validate()

        if res is True and self.env.context.get('purchase_import_id'):
            Purchase = self.env['purchase.import']
            purchase_import_id = self.env.context.get('purchase_import_id')
            purchase_import = Purchase.browse(purchase_import_id)
            purchase_import.action_done()

        return res
