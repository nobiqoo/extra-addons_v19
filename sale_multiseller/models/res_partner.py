# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    seller_ids = fields.Many2many(
        comodel_name='res.users',
        relation='res_partner_seller_rel',
        column1='partner_id',
        column2='user_id',
        string="Assigned Salespeople",
        help="Salespeople who can see, edit and use this contact in quotations, sales orders and the Point of Sale. "
             "Its addresses and contacts follow the salespeople of the company.",
    )
    assigned_seller_ids = fields.Many2many(
        comodel_name='res.users',
        relation='res_partner_assigned_seller_rel',
        column1='partner_id',
        column2='user_id',
        string="Effective Salespeople",
        compute='_compute_assigned_seller_ids',
        store=True,
        recursive=True,
    )

    @api.depends('seller_ids', 'parent_id.assigned_seller_ids')
    def _compute_assigned_seller_ids(self):
        for partner in self:
            partner.assigned_seller_ids = partner.parent_id.assigned_seller_ids if partner.parent_id else partner.seller_ids

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        if not self.env.su and not bypass_access:
            self.flush_model(['assigned_seller_ids'])
        return super()._search(domain, offset=offset, limit=limit, order=order,
                               active_test=active_test, bypass_access=bypass_access)

    @api.model_create_multi
    def create(self, vals_list):
        restricted = self.env.user.has_group('sale_multiseller.group_restricted_salesperson')
        for vals in vals_list:
            if vals.get('parent_id'):
                continue
            commands = vals.get('seller_ids') or []
            if commands and not isinstance(commands[0], (list, tuple)):
                commands = [Command.set(commands)]
            extra = [Command.link(uid) for uid in {self.env.uid if restricted else False, vals.get('user_id')} if uid]
            if extra:
                vals['seller_ids'] = list(commands) + extra
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'user_id' in vals or 'seller_ids' in vals:
            roots = self.filtered(lambda p: p.user_id and not p.parent_id and p.user_id not in p.seller_ids)
            if 'user_id' in vals:
                # Comercial nuevo: se agrega a los vendedores asignados
                for user, partners in roots.grouped('user_id').items():
                    partners.write({'seller_ids': [Command.link(user.id)]})
            else:
                roots.write({'user_id': False})
        return res
