from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    res_users_sale_activity = fields.Many2many(
        'res.users',
        string='Usuarios que deben ser notificados',
    )
