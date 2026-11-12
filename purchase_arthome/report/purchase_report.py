# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.tools import SQL

from ..models.purchase_order import PURCHASE_CATEGORIES


class PurchaseReport(models.Model):
    _inherit = 'purchase.report'

    purchase_category = fields.Selection(selection=PURCHASE_CATEGORIES, string='Purchase Type', readonly=True)

    def _select(self) -> SQL:
        return SQL("%s, po.purchase_category AS purchase_category", super()._select())

    def _group_by(self) -> SQL:
        return SQL("%s, po.purchase_category", super()._group_by())
