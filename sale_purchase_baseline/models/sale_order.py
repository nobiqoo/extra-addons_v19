# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        for order in self:
            if order.company_id.block_contact_without_account_position and \
                    not order.partner_id.property_account_position_id:
                raise ValidationError(
                    _("Blocking error, in order to confirm the quotation please make sure that the customer has a fiscal position,\n"
                      "please contact Accounting to release the contact."))
        return super().action_confirm()