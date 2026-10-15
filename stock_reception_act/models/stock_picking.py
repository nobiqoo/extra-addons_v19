# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    reception_area = fields.Char(
        string='Reception Area',
    )
    reception_site = fields.Char(
        string='Site',
    )
    reception_product_type = fields.Selection(
        selection=[
            ('medical_device', 'Medical Devices'),
            ('supply', 'Supplies'),
        ],
        string='Product Type',
    )
    reception_responsible_id = fields.Many2one(
        comodel_name='res.users',
        string='Reception Responsible',
        default=lambda self: self.env.user,
    )

    def _get_reception_act_title(self):
        """El acta es siempre un documento en español, sin importar el idioma
        configurado en el contacto del proveedor."""
        self.ensure_one()
        if self.return_id:
            return 'ACTA DE DEVOLUCIÓN'
        if self.picking_type_code == 'incoming':
            return 'ACTA DE RECEPCIÓN'
        return 'ACTA DE INVENTARIO'
