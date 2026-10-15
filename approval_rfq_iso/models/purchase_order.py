# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_request_origin_id = fields.Many2one(
        comodel_name='approval.request',
        string='Aprobacion origen',
        copy=False,
        index=True,
        readonly=True,
        help='Solicitud de aprobacion que genero esta cotizacion/orden de compra.',
    )
