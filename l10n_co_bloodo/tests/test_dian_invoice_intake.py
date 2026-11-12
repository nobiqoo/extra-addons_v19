# -*- coding: utf-8 -*-
import base64

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_dian_document_xml import INVOICE_XML


@tagged('post_install', '-at_install')
class TestDianInvoiceIntake(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.intake = cls.env['dian.invoice.intake'].create({'company_id': cls.company.id})
        cls.xml_b64 = base64.b64encode(INVOICE_XML)
        cls.werte = {
            'UUID': 'CUFE-MAIL',
            'ID': 'FV-MAIL',
            'AccountingSupplierParty': {'Name': 'Proveedor', 'CompanyID': '900123'},
        }

    def _existing_document(self, **vals):
        return self.env['dian.document'].create(dict({
            'cufe': 'CUFE-MAIL',
            'name': 'FV-MAIL',
            'reception': fields.Datetime.now(),
            'company_id': self.company.id,
            'type': 'Factura electrónica',
            'total_amount': 7.0,
        }, **vals))

    def test_creates_missing_document(self):
        document, outcome = self.intake._upsert_dian_document(self.werte, self.xml_b64)
        self.assertEqual(outcome, 'created')
        self.assertEqual(document.xml_state, 'done')
        self.assertEqual(document.type, 'Factura electrónica')
        self.assertEqual(document.total_amount, 119.0)
        self.assertEqual(document.tax_amount_19_percent, 19.0)
        self.assertEqual(len(document.invoice_line_ids), 1)

    def test_fills_pending_document_without_duplicating(self):
        existing = self._existing_document(xml_state='error')
        document, outcome = self.intake._upsert_dian_document(self.werte, self.xml_b64)
        self.assertEqual((document, outcome), (existing, 'filled'))
        self.assertEqual(self.env['dian.document'].search_count([('cufe', '=', 'CUFE-MAIL')]), 1)
        self.assertEqual(existing.xml_state, 'done')
        self.assertEqual(existing.payable_amount, 119.0)
        # Portal values are kept
        self.assertEqual(existing.total_amount, 7.0)

    def test_keeps_document_that_already_has_xml(self):
        existing = self._existing_document(xml_state='done', payable_amount=1.0)
        document, outcome = self.intake._upsert_dian_document(self.werte, self.xml_b64)
        self.assertEqual((document, outcome), (existing, 'done'))
        self.assertEqual(existing.payable_amount, 1.0)
        self.assertFalse(existing.invoice_line_ids)

    def test_leaves_document_being_processed_to_the_cron(self):
        existing = self._existing_document(
            xml_state='processing', xml_processing_since=fields.Datetime.now())
        document, outcome = self.intake._upsert_dian_document(self.werte, self.xml_b64)
        self.assertEqual((document, outcome), (existing, 'processing'))
        self.assertEqual(existing.xml_state, 'processing')
        self.assertFalse(existing.invoice_line_ids)

    def test_retry_only_for_accounting_managers(self):
        billing_user = new_test_user(
            self.env, login='intake_billing',
            groups='account.group_account_invoice,l10n_co_bloodo.group_dian_invoice_intake')
        with self.assertRaises(AccessError):
            self.intake.with_user(billing_user).action_retry()
