from odoo import api, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    @api.onchange('move_raw_ids', 'move_byproduct_ids')
    def _onchange_stock_felupe_cost_sharing(self):
        for production in self:
            production.move_byproduct_ids._compute_cost_sharing()
