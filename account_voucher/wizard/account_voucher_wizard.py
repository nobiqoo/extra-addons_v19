# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class AccountVoucherWizard(models.TransientModel):
    _name = 'account.voucher.wizard'
    _description = 'Accounting Voucher Wizard'

    def _default_journal_id(self):
        domain = [('type', 'in', ('cash', 'bank'))]
        return self.env['account.journal'].search(domain, limit=1)

    active_bool = fields.Boolean(string='Many', default=False)

    amount = fields.Monetary(string='Amount')

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        readonly=False,
        default=lambda self: self.env.company.currency_id,
        help="The voucher's currency."
    )

    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        required=True
    )

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Journal',
        required=True,
        default=_default_journal_id
    )

    voucher_reference = fields.Char(
        string="Voucher Reference",
        help="Reference of the document used to issue this voucher. Eg. check number, file name, etc."
    )

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id and not self.currency_id:
            currency_id = self.journal_id.currency_id or self.company_id.currency_id
            self.update({
                'currency_id': currency_id.id
            })

    def button_create_voucher(self):
        model = self._context.get('active_model')
        ids = self._context.get('active_ids')
        if not model:
            return False
        actives = self.env[model].browse(ids)
        for active in actives:
            if active.move_type not in ('out_invoice', 'in_invoice'):
                continue
            if active.payment_state in ('paid'):
                continue
            values = {
                'voucher_type': 'voucher',
                'partner_type': active.move_type == 'out_invoice' and 'customer' or 'supplier',
                'company_id': active.company_id.id,
                'partner_id': active.partner_id.id,
                'journal_id': self.journal_id.id,
                'account_id': active.move_type == 'out_invoice' and active.partner_id.property_account_receivable_id.id or active.partner_id.property_account_payable_id.id,
                'date': self.date,
                'amount': self.active_bool and active.amount_residual or self.amount,
                'currency_id': self.active_bool and active.currency_id.id or self.currency_id.id,
                'voucher_date': self.date,
                'voucher_reference': self.active_bool and active.name or self.voucher_reference,
            }
            voucher = self.env['account.voucher'].create(values)
            voucher.with_context(
                line_ids=active.line_ids.ids).compute_line_ids()
            voucher.action_post()
        return True
