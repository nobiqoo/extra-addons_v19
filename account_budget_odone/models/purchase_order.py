
# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_request_approval(self):
        for order in self:
            if order.state not in ['draft', 'sent']:
                continue

            if not order.order_line:
                raise UserError(_("Registre línea(s) de Orden de Compra antes de continuar."))

            if self.env.company.purchase_budget_controll:
                order.order_line._get_budget_data()

            if self.env.company.pr_approval_po:
                order.approval_with_sequence = order.approval_config_id.approval_with_sequence
                approval_ids = order.approval_config_id.approval_line_ids
                sequence = 0
                total_values = []

                for approvers in approval_ids:
                    if self.env.company.currency_id != self.currency_id:
                        amount_currency_total = self.currency_id._convert(
                            self.amount_untaxed, self.env.company.currency_id, self.company_id, fields.Datetime.now()
                        )
                    else:
                        amount_currency_total = self.amount_untaxed

                    if (approvers.approval_type == 'by_amount' and 
                        amount_currency_total >= approvers.amount_from) or approvers.approval_type == 'without_condition':
                        if order.approval_with_sequence:
                            sequence += 1
                        else:
                            sequence = 1

                    if (approvers.approval_type == 'by_amount' and 
                        amount_currency_total >= approvers.amount_from) or approvers.approval_type == 'without_condition':
                        values = {
                            'sequence': sequence,
                            'approval_config_id': self.approval_config_id.id,
                            'company_id': self.env.user.company_id.id,
                            'user_ids': approvers.user_ids,
                            'purchase_order_id': self.id,
                            'required': False,
                            'status': 'pending' if sequence == 1 else 'waiting',
                            'amount_from': approvers.amount_from,
                            'approval_type': approvers.approval_type,
                        }
                        total_values.append((0, 0, values))

                self.approval_ids = total_values
                order.action_create_approval_activity()
                order.write({'state': 'in approval',})
                
    def button_confirm(self):
        for order in self:
            if self.env.context.get('skip_approval'):
                super().button_confirm()
                continue
            if order.state not in ['sent','approved'] and self.env.company.pr_approval_po:
                continue

            if order.state != 'approved' and self.env.company.pr_approval_po:
                raise UserError(_("La Orden de Compra no ha sido aprobada aún."))

            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()

            if self.env.company.purchase_budget_controll:
                validation = order.check_available_budget()
                if validation != True:
                    return validation
            
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})

            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])

        return True