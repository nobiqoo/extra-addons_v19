# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    vendor_contact_id = fields.Many2one(
        'res.partner',
        string='Contacto del Proveedor',
        help='Persona de contacto del proveedor que se imprime en el bloque '
             '"Vendedor" del reporte de la orden de compra.',
    )
