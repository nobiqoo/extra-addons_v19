# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountPaymentLineCreate(models.TransientModel):
    _inherit = "account.payment.line.create"

    payslip_processing_ids = fields.Many2many(
        'hr.payslip.processing', string='Procesamientos de Nóminas')
    bank_id = fields.Many2one('res.bank', string='Banco a pagar')

    @api.depends(
        "date_type",
        "journal_ids",
        "invoice",
        "target_move",
        "payment_mode",
        "partner_ids",
        "payslip_processing_ids",
        "bank_id",
    )
    def _compute_move_line_domain(self):
        super()._compute_move_line_domain()
        for record in self:
            domain = record.move_line_domain or []
            if record.payslip_processing_ids:
                concepts_to_pay = [
                    'NETO A PAGAR', 'NETO A PAGAR CESANTIAS', 'NETO A PAGAR LIQUIDACION'
                ]

                moves_lines = record.payslip_processing_ids.mapped(
                    'payslips_ids.move_id.line_ids'
                ).filtered(lambda m: m.name in concepts_to_pay)

                if record.bank_id:
                    moves_lines = moves_lines.filtered(
                        lambda m: record.bank_id.id in m.partner_id.bank_ids.mapped(
                            'bank_id').ids
                    )

                domain += [("id", "in", moves_lines.ids)]
            record.move_line_domain = domain
