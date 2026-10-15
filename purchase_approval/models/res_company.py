# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

class ResCompany(models.Model):
    _inherit = 'res.company'

    pr_approval_po = fields.Boolean(
        string="Flujo de aprobación orden de compra",
        default=True
    )
    purchase_budget_controll = fields.Boolean(
        string='Control Presupuestal en Ordenes de Compra',
        default=False
    )
