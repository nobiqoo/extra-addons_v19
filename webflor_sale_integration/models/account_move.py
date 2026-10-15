from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    city_id = fields.Many2one(
        'res.city',
        string='Ciudad',
        compute='_compute_city_id',
        store=True,
        readonly=False,
        precompute=True,
    )

    @api.depends('partner_id', 'partner_id.city', 'partner_id.city_id')
    def _compute_city_id(self):
        for move in self:
            if move.state != 'draft':
                continue
            move.city_id = move.partner_id._get_or_create_city() if move.partner_id else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.pop('city_id', None)
        return res
