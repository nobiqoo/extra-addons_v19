# -*- coding: utf-8 -*-

from datetime import datetime
from unittest.mock import patch

from odoo import fields
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.base.models.ir_sequence import IrSequence


@tagged("-at_install", "post_install")
class TestAccountMoveSequenceDate(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_notrack=True,
                no_reset_password=True,
                tracking_disable=True,
            )
        )
        cls.journal = cls.company_data["default_journal_sale"]
        if not cls.journal.sequence_id:
            cls.journal.create_journal_sequence()

    def test_action_post_uses_datetime_sequence_date(self):
        captured = {}
        move_date = fields.Date.from_string("2024-06-15")

        original_next_by_id = IrSequence.next_by_id

        def _next_by_id(sequence_self):
            if sequence_self == self.journal.sequence_id:
                captured["ir_sequence_date"] = sequence_self.env.context.get(
                    "ir_sequence_date"
                )
            return original_next_by_id(sequence_self)

        move_form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        move_form.partner_id = self.partner_a
        move_form.invoice_date = move_date
        with move_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product_a
            line_form.quantity = 1
            line_form.price_unit = 100
            line_form.account_id = self.company_data["default_account_revenue"]
        move = move_form.save()

        with patch.object(IrSequence, "next_by_id", autospec=True, side_effect=_next_by_id):
            move.action_post()

        self.assertIsInstance(captured["ir_sequence_date"], datetime)
        self.assertEqual(captured["ir_sequence_date"].date(), move.date)
