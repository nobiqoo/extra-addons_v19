# -*- coding: utf-8 -*-

from odoo import fields, models

class PurchaseApprovalLine(models.Model):
    _name = 'purchase.approval.line'
    _description = 'Purchase Approval Line'
    _order = 'sequence'

    company_id = fields.Many2one(
        comodel_name='res.company',
        related='purchase_approval_id.company_id'
    )
    purchase_approval_id = fields.Many2one(
        comodel_name='purchase.approval.setting',
        string='Configuración de Aprobación'
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='approval_line_user_rel',
        column1='approval_line_id',
        column2='user_id',
        string='Usuarios',
    )
    is_required = fields.Boolean(
        string='Requerido'
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
