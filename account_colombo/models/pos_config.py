# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    """Punto de venta con sede de operación (tarea 10340).

    La sede se configura en el punto de venta, no en cada pedido: una caja
    atiende siempre desde la misma ubicación física y el cajero no tiene por
    qué conocer la tarifa del municipio.
    """

    _inherit = 'pos.config'

    operation_site_id = fields.Many2one(
        'account.operation.site',
        string="Sede de Operación",
        check_company=True,
        help="Sede desde la que opera esta caja. Las líneas de los pedidos "
             "nacen con el ReteICA de venta configurado en la sede, además de "
             "los impuestos propios del producto.")
    reteica_tax_id = fields.Many2one(
        'account.tax',
        string="ReteICA de la sede",
        related='operation_site_id.sale_reteica_tax_id',
        readonly=True,
        help="Impuesto que la caja aplica a cada línea. Se expone al frontend "
             "del punto de venta para que el ticket y el asiento contable "
             "calculen exactamente lo mismo.")

    @api.model
    def _load_pos_data_fields(self, config):
        """Expone la sede y su impuesto al frontend del punto de venta.

        Cuando la lista viene vacía el POS ya carga todos los campos, así que
        solo hay que completarla si el core (o algún otro módulo) la acotó.
        """
        fields_list = super()._load_pos_data_fields(config)
        if fields_list:
            for fname in ('operation_site_id', 'reteica_tax_id'):
                if fname not in fields_list:
                    fields_list.append(fname)
        return fields_list
