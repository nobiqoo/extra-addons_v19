# -*- coding: utf-8 -*-

import json

from odoo import _, api, fields, models


class AccountDetails(models.TransientModel):
    _name = 'account.details.wizard'
    _description = 'Account Details Report'

    date_start = fields.Date(
        required=True,
        default=fields.Date.today
    )
    date_end = fields.Date(
        required=True,
        default=fields.Date.today
    )

    moves_ids = fields.Many2many('account.move')
    move_type = fields.Selection(
        selection=[
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
        ],
        default='out_invoice',
        string='Invoice Type',
        required=True
    )

    user_id = fields.Many2one(
        comodel_name='res.users',
        required=True,
        default=lambda self: self.env.user
    )

    @api.onchange('date_start')
    def _onchange_date_start(self):
        if self.date_start and self.date_end and self.date_end < self.date_start:
            self.date_end = self.date_start

    @api.onchange('date_end')
    def _onchange_date_end(self):
        if self.date_end and self.date_end < self.date_start:
            self.date_start = self.date_end

    def generate_report(self):
        Move = self.env['account.move']
        move_domain = [
            ('state', '=', 'posted'),
            ('move_type', '=', self.move_type),
            ('date', '>=', self.date_start),
            ('date', '<=', self.date_end),
        ]
        moves = Move.search(move_domain)
        self.moves_ids = moves

        report = self.env.ref(
            'account_baseline.action_report_account_details_wizard'
        )
        return report.report_action(self)

    def invoice_payments_widget(self, move):
        widget = move.invoice_payments_widget
        payments = self._get_widget_value(widget)
        return payments and payments.get('content', []) or []

    def tax_totals_json(self, move):
        widget = getattr(move, 'tax_totals', False) or getattr(move, 'tax_totals_json', False)
        widget_json = self._get_widget_value(widget)
        subtotals = widget_json.get('subtotals') or []
        groups_by_subtotal = widget_json.get('groups_by_subtotal') or {}
        if groups_by_subtotal:
            return subtotals and groups_by_subtotal.get(subtotals[0].get('name')) or []
        return [
            {
                'tax_group_name': tax_group.get('group_name'),
                'tax_group_base_amount': tax_group.get('base_amount_currency', 0.0),
                'tax_group_amount': tax_group.get('tax_amount_currency', 0.0),
            }
            for subtotal in subtotals
            for tax_group in subtotal.get('tax_groups', [])
        ]

    def _get_widget_value(self, widget):
        if not widget:
            return {}
        if isinstance(widget, dict):
            return widget
        if isinstance(widget, bytes):
            widget = widget.decode()
        return json.loads(widget)
