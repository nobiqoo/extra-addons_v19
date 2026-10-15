from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    res_users_sale_activity = fields.Many2many(
        related='company_id.res_users_sale_activity',
        readonly=False,
        string='Usuarios que deben ser notificados',
    )
