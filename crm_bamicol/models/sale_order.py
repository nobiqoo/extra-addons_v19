# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'


    architect_id = fields.Many2one(
        comodel_name='res.partner',
        string='Arquitecto',
        tracking=True,
        index=True,
        help=(
            'Arquitecto asociado a esta '
            'cotización/pedido de venta. Obligatorio cuando el equipo de '
            'ventas tenga activada la opción "Requiere Arquitecto".'
        ),
    )

    architect_required = fields.Boolean(
        string='Arquitecto obligatorio',
        compute='_compute_architect_required',
        store=False,
    )

    @api.depends('team_id', 'team_id.require_architect')
    def _compute_architect_required(self):
        for order in self:
            order.architect_required = bool(
                order.team_id and order.team_id.require_architect
            )

    @api.constrains('architect_id', 'team_id')
    def _check_architect_required(self):
        for order in self:
            if (
                order.team_id
                and order.team_id.require_architect
                and not order.architect_id
            ):
                raise ValidationError(
                    'El campo "Arquitecto" es obligatorio para el equipo de '
                    f'ventas "{order.team_id.name}". '
                    'Por favor seleccione un arquitecto antes de guardar.'
                )

    @api.model_create_multi
    def create(self, vals_list):
        default_architect = self.env.context.get('default_architect_id')
        if default_architect:
            for vals in vals_list:
                if not vals.get('architect_id'):
                    vals['architect_id'] = default_architect
        return super().create(vals_list)
