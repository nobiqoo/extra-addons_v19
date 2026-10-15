# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, Command


class AssetModify(models.TransientModel):
    _inherit = 'asset.modify'

    def sell_dispose(self):
        res = super().sell_dispose()
        self.asset_id.discharge_date = self.date
        return res
