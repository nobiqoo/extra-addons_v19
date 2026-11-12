from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    use_signed_work_orders_in_maintenance = fields.Boolean(
        string='Usar firmas en órdenes de trabajo de mantenimiento',
        default=False,
    )
