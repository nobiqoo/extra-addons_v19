# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

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
            ('by_amount', 'Por monto'),
            ('range', 'Rango'),
        ],
        string='Tipo de Aprobación',
        default='without_condition'
    )
    amount_from = fields.Float(
        string='A partir de / Desde'
    )
    amount_to = fields.Float(
        string='Hasta'
    )

    @api.constrains('approval_type', 'amount_from', 'amount_to')
    def _check_range_amounts(self):
        # Solo valida el propio registro (Hasta > Desde). Las validaciones que
        # comparan varias líneas entre sí (tipos mezclados, superposición, huecos)
        # viven en purchase.approval.setting._check_matrix_consistency, llamada
        # explícitamente tras escribir/crear, en vez de con @api.constrains: Odoo
        # procesa los comandos de un one2many uno por uno, y un @api.constrains
        # aquí se dispara en cada paso intermedio (p.ej. cuando la línea 1 ya
        # quedó en "Rango" pero la línea 2 todavía no), bloqueando guardados
        # legítimos que sí son consistentes en su estado final.
        for record in self:
            if record.approval_type == 'range' and record.amount_to <= record.amount_from:
                raise ValidationError(_(
                    'En la línea de aprobación de "%s" el valor "Hasta" debe ser mayor al valor "Desde".',
                    ', '.join(record.user_ids.mapped('name')) or record.purchase_approval_id.name or ''
                ))
