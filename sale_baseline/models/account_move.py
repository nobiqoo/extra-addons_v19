# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_edit_salesperson = fields.Boolean(
        'Salesperson editable',
        compute='_compute_is_editable_salesperson'
    )
    refund_for_higher_value = fields.Boolean(
        string='Refund for higher value',
        default=False)

    @api.depends('company_id',
                 'company_id.salesperson_not_editable',
                 'move_type')
    def _compute_is_editable_salesperson(self):
        for record in self:
            editable = False
            if record.company_id.salesperson_not_editable and \
                    record.move_type in ('out_invoice', 'out_refund'):
                user_id = self.env.user
                if user_id.has_group('sale_baseline.group_edit_salesperson'):
                    editable = True
            else:
                editable = True
            record.is_edit_salesperson = editable
