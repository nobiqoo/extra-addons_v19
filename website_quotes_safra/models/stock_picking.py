# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    """Ajustes Sprint 1.6 (26-oct, filas 126 y 128): la factura al validar
    la entrega es la de stock_baseline (Ajustes de Ventas › Crear facturas
    desde la transferencia, con el diario del almacén). Los pedidos del
    cotizador de exportación o de proyectos especiales quedan por fuera: se
    agrupan y se facturan a mano."""
    _inherit = 'stock.picking'

    def button_validate(self):
        manuales = self.filtered(lambda p: p.picking_type_code == 'outgoing'
                                 and p.sale_id.safra_facturacion_manual)
        res = super(StockPicking, self.with_context(safra_sin_factura_entrega=True)).button_validate()
        if res is True and self.env.company.create_invoices_from_picking:
            for picking in manuales.filtered(lambda p: p.state == 'done'):
                picking.message_post(body=(
                    'Pedido de exportación o de proyectos especiales: no se factura al '
                    'despachar; se agrupa y se factura a mano desde Ventas.'))
        return res
