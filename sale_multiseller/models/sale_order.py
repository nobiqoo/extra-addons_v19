# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    allowed_user_ids = fields.Many2many(
        comodel_name='res.users',
        string="Allowed Salespeople",
        compute='_compute_allowed_user_ids',
        compute_sudo=True,
    )

    @api.depends('partner_id.assigned_seller_ids', 'company_id')
    def _compute_allowed_user_ids(self):
        """Calcula los vendedores asignados al cliente o, si no tiene, todos los vendedores de la compañía."""
        salesman_group = self.env.ref('sales_team.group_sale_salesman')
        salespeople_by_company = {}
        for order in self:
            sellers = order.partner_id.assigned_seller_ids
            if not sellers:
                company = order.company_id
                if company not in salespeople_by_company:
                    salespeople_by_company[company] = self.env['res.users'].search([
                        ('all_group_ids', 'in', salesman_group.ids),
                        ('share', '=', False),
                        ('company_ids', 'in', company.ids),
                    ])
                sellers = salespeople_by_company[company]
            order.allowed_user_ids = sellers

    def _compute_user_id(self):
        """Mantiene el vendedor dentro de los vendedores asignados al cliente al elegirlo."""
        super()._compute_user_id()
        restricted = self.env.user.has_group('sale_multiseller.group_restricted_salesperson')
        for order in self:
            if order._origin.id and order.partner_id == order._origin.partner_id:
                continue
            if restricted:
                order.user_id = self.env.user
                continue
            sellers = order.partner_id.sudo().assigned_seller_ids
            if not sellers or order.user_id in sellers:
                continue
            candidates = (order.partner_id.commercial_partner_id.sudo().user_id | self.env.user) & sellers
            order.user_id = candidates[:1]
