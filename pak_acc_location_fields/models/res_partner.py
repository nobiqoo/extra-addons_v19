from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_guatemala_localization = fields.Boolean(compute='_compute_is_gt_localization')

    def _compute_is_gt_localization(self):
        for record in self:
            record.is_guatemala_localization = self.env.company.chart_template == 'gt'
