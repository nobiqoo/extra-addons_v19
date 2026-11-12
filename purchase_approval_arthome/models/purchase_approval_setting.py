# -*- coding: utf-8 -*-

from odoo import fields, models


class PurchaseApprovalSetting(models.Model):
    _inherit = 'purchase.approval.setting'

    ask_alternatives_on_auto_confirm = fields.Boolean(
        string='Ask About Alternatives',
        help='When the approval completes an order that still has open alternative quotations, '
             'the order stays approved and the approver is asked whether to cancel or keep them. '
             'If unchecked, the order is confirmed automatically and the alternatives remain open.',
        default=True,
    )
