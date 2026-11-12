from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_signed_work_orders_in_maintenance = fields.Boolean(
        string='Usar firmas en órdenes de trabajo de mantenimiento',
        related='company_id.use_signed_work_orders_in_maintenance',
        readonly=False,
    )
