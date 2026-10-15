# -*- coding: utf-8 -*-

from odoo import models, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        for order in self:
            if order.company_id.block_contact_without_account_position and \
                    not order.partner_id.property_account_position_id:
                raise ValidationError(
                    _("Blocking error, in order to confirm the purchase please make sure that the customer has a fiscal position,\n"
                      "please contact Accounting to release the contact."))
        return super().button_confirm()
