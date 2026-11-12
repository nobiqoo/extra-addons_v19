# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    """Prueba 126.1 (26-oct): pedido de venta generado por una cotización
    del cotizador; la marca de exportación permite filtrar y agrupar los
    pedidos de una negociación en una factura consolidada."""
    _inherit = 'sale.order'

    safra_quote_id = fields.Many2one('safra.quote', string='Cotización Safra',
                                     readonly=True, copy=False, index=True)
    safra_exportacion = fields.Boolean(string='Exportación (cotizador)',
                                       related='safra_quote_id.es_exportacion', store=True)
    # Ajustes Sprint 1.6 (26-oct, filas 126 y 128): exportación y proyectos
    # especiales no se facturan al despachar; se agrupan y se facturan a mano.
    safra_proyecto_especial = fields.Boolean(
        string='Proyectos especiales (cotizador)',
        related='safra_quote_id.es_proyecto_especial', store=True)
    safra_facturacion_manual = fields.Boolean(
        string='Facturación manual (cotizador)', compute='_compute_safra_facturacion_manual',
        store=True, help='Exportación o proyectos especiales: no se factura al despachar.')
    # Fila 127: embalaje del pedido, para despachos y la lista de materiales.
    safra_embalaje_ids = fields.Many2many(
        related='safra_quote_id.embalaje_ids', string='Embalaje (cotizador)')
    # Datos de despacho del cotizador (filas 184-188), para despachos.
    safra_recoge_fabrica = fields.Boolean(related='safra_quote_id.recoge_fabrica')
    safra_despacho_country_id = fields.Many2one(related='safra_quote_id.despacho_country_id')
    safra_despacho_city_id = fields.Many2one(related='safra_quote_id.despacho_city_id')
    safra_despacho_direccion = fields.Char(related='safra_quote_id.despacho_direccion')
    safra_despacho_destinatario = fields.Char(related='safra_quote_id.despacho_destinatario')
    safra_despacho_fecha = fields.Date(related='safra_quote_id.despacho_fecha')

    @api.depends('safra_exportacion', 'safra_proyecto_especial')
    def _compute_safra_facturacion_manual(self):
        for order in self:
            order.safra_facturacion_manual = order.safra_exportacion or order.safra_proyecto_especial

    def _get_invoiceable_lines(self, final=False):
        """Al validar la entrega (stock_baseline), los pedidos de exportación
        o de proyectos especiales no tienen qué facturar: así no se crea la
        factura y no se pide el diario del almacén."""
        lines = super()._get_invoiceable_lines(final)
        if self.env.context.get('safra_sin_factura_entrega'):
            lines = lines.filtered(lambda l: not l.order_id.safra_facturacion_manual)
        return lines
