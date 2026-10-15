# -*- coding: utf-8 -*-

from odoo import fields, models

class PurchaseOrderApproval(models.Model):
    _name = 'purchase.order.approval'
    _description = 'Purchase Order Approval'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Orden de Compra'
    )    
    approval_config_id = fields.Many2one(
        comodel_name='purchase.approval.setting', 
        string='Configuración Aprobación', 
        ondelete='cascade', 
        related='purchase_order_id.approval_config_id'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        related='approval_config_id.company_id'
    )
    user_ids = fields.Many2many(
        comodel_name='res.users',
        string='Usuario'
    )
    required = fields.Boolean(
        string='Requerido',
        default=False
    )
    status = fields.Selection(
        selection=[
            ('new', 'New'),
            ('pending', 'Por Aprobar'),
            ('waiting', 'Esperando'),
            ('approved', 'Aprobado'),
            ('refused', 'Rechazado'),
            ('cancel', 'Anulado')
        ], 
        string="Estado",
        default="new",
        readonly=True
    )
    approval_type = fields.Selection(
        selection=[
            ('without_condition', 'Sin Condición'),
            ('by_amount', 'Por monto')
        ],
        string='Tipo de Aprobación',
        default='without_condition'
    )
    amount_from = fields.Float(
        string='A partir de'
    )
