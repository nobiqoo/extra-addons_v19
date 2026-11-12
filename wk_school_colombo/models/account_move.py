# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    installment_plan_id = fields.Many2one(
        'wk.fee.installment.plan', string='Acuerdo de pago por cuotas',
        compute='_compute_installment_plan_id')

    @api.depends('fee_slip_id')
    def _compute_installment_plan_id(self):
        plans = self.env['wk.fee.installment.plan'].search(
            [('invoice_id', 'in', self.ids)])
        plan_by_invoice = {plan.invoice_id.id: plan for plan in plans}
        for move in self:
            move.installment_plan_id = plan_by_invoice.get(move.id, False)
