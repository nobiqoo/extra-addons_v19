from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_guatemala_localization = fields.Boolean(compute='_is_gt_location')

    def _is_gt_location(self):
        for record in self:
            record.is_guatemala_localization = self.env.company.chart_template == 'gt'
