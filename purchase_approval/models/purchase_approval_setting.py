# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import ValidationError

class PurchaseApprovalSetting(models.Model):
    _name = 'purchase.approval.setting'
    _description = 'Purchase Approval Setting'

    name = fields.Char(
        string='Nombre de Matriz'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda'
    )
    approval_coordinador_id = fields.Many2one(
        comodel_name='res.users', 
        string='Coordinador'
    )
    approval_analyst_ids = fields.Many2many(
        comodel_name='res.users',
        relation='purchase_approval_user_rel',
        column1='purchase_approval_id',
        column2='user_id',
        string='Analistas'
    )
    approval_with_sequence = fields.Boolean(
        string='Aprobación con Secuencia',
        help='En caso de que este marcado los aprobadores deben aprobar en secuencia',
        default=False
    )
    approval_line_ids = fields.One2many(
        comodel_name='purchase.approval.line',
        string='Líneas de Aprobación',
        inverse_name='purchase_approval_id'
    )
    approval_automatic = fields.Boolean(
        string='Confirmación Automatica',
        help='En caso de que este marcado se pasará la orden a confirmado cuando se realicen las aprobaciones',
        default=False
    )
    approval_minimum = fields.Integer(
        string="Aprobadores minimos",
        default=1,
    )
    user_approvals_by_budget = fields.Many2many(
        comodel_name='res.users',
        relation='purchase_setting_user_rel',
        column1='setting_id',
        column2='user_id',
        string='Aprobadores por falta de presupuesto'
    )
    is_default_to_purchase = fields.Boolean(
        string='Usar por defecto en compras',
    )

    @api.constrains("is_default_to_purchase")
    def _check_is_default_to_purchase(self):
        for record in self:
            if record.is_default_to_purchase:
                default_purchase = self.env['purchase.approval.setting'].search([
                    ('id', '!=', record.id),
                    ('company_id', '=', record.company_id.id),
                    ('is_default_to_purchase', '=', True)
                ])
                if default_purchase:
                    raise ValidationError('Ya existe una matriz '
                                          'marcada para usar por '
                                          'defecto en compras. [{name}]'.format(name=default_purchase.name))
