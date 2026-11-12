# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.dian_document_xml import XML_MAX_ATTEMPTS, XML_STALE_MINUTES

UBL_NS = (
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
)

INVOICE_XML = f'''<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" {UBL_NS}>
    <cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>COP</cbc:DocumentCurrencyCode>
    <cac:OrderReference><cbc:ID>P00042</cbc:ID></cac:OrderReference>
    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="COP">19.00</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="COP">100.00</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="COP">19.00</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:Percent>19.00</cbc:Percent>
                <cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="COP">100.00</cbc:LineExtensionAmount>
        <cbc:PayableAmount currencyID="COP">119.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
    <cac:InvoiceLine>
        <cbc:ID>1</cbc:ID>
        <cbc:InvoicedQuantity unitCode="94">2</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="COP">100.00</cbc:LineExtensionAmount>
        <cac:Item><cbc:Description>Producto</cbc:Description></cac:Item>
        <cac:Price><cbc:PriceAmount currencyID="COP">50.00</cbc:PriceAmount></cac:Price>
    </cac:InvoiceLine>
</Invoice>'''.encode()

DEBIT_NOTE_XML = f'''<?xml version="1.0" encoding="UTF-8"?>
<DebitNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2" {UBL_NS}>
    <cac:DiscrepancyResponse>
        <cbc:ReferenceID>FV-1</cbc:ReferenceID>
        <cbc:ResponseCode>3</cbc:ResponseCode>
    </cac:DiscrepancyResponse>
    <cac:RequestedMonetaryTotal>
        <cbc:PayableAmount currencyID="COP">10.00</cbc:PayableAmount>
    </cac:RequestedMonetaryTotal>
    <cac:DebitNoteLine>
        <cbc:ID>1</cbc:ID>
        <cbc:DebitedQuantity unitCode="94">3</cbc:DebitedQuantity>
        <cbc:LineExtensionAmount currencyID="COP">10.00</cbc:LineExtensionAmount>
    </cac:DebitNoteLine>
</DebitNote>'''.encode()


@tagged('post_install', '-at_install')
class TestDianDocumentXml(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.type_einvoicing = 'edi_dir'
        cls.Document = cls.env['dian.document']
        cls.sync = cls.env['dian.sync'].create({
            'document_ids': [
                (0, 0, {
                    'cufe': 'CUFE-%s' % i,
                    'name': 'FV-%s' % i,
                    # Older than any real document, so the cron picks them first
                    'reception': datetime(2000, 1, 1) + timedelta(days=i),
                }) for i in range(3)
            ],
        })
        cls.documents = cls.sync.document_ids.sorted('reception')

    def _process(self, document):
        """Process the document as the cron does: only once it has been claimed."""
        document.write({'xml_state': 'processing', 'xml_processing_since': fields.Datetime.now()})
        document._xml_process()

    def _patch_fetch(self, result):
        return patch.object(type(self.Document), '_fetch_xml_content',
                            autospec=True, return_value=result)

    def test_parse_debit_note(self):
        vals = self.Document._xml_to_document_vals(DEBIT_NOTE_XML)
        self.assertEqual(vals['invoice_type'], '92')
        self.assertEqual(vals['discrepancy_reference_id'], 'FV-1')
        self.assertEqual(vals['payable_amount'], 10.0)
        self.assertEqual(vals['invoice_line_ids'][0][2]['invoiced_quantity'], 3.0)

    def test_cron_success_fills_data(self):
        self.assertEqual(self.sync.xml_state, 'pending')
        with self._patch_fetch({'status': 'success', 'xml_content': INVOICE_XML}):
            self.Document._cron_fetch_xml(batch_size=10)
        self.assertEqual(set(self.documents.mapped('xml_state')), {'done'})
        document = self.documents[0]
        self.assertEqual(document.invoice_type, '01')
        self.assertEqual(document.order_reference, 'P00042')
        self.assertEqual(document.payable_amount, 119.0)
        self.assertEqual(len(document.invoice_line_ids), 1)
        self.assertEqual(len(document.tax_total_ids), 1)
        self.assertEqual(self.sync.xml_state, 'done')

    def test_reprocess_replaces_lines(self):
        document = self.documents[0]
        with self._patch_fetch({'status': 'success', 'xml_content': INVOICE_XML}):
            self._process(document)
            self._process(document)
        self.assertEqual(len(document.invoice_line_ids), 1)
        self.assertEqual(len(document.tax_total_ids), 1)

    def test_batch_size_and_order(self):
        with self._patch_fetch({'status': 'success', 'xml_content': INVOICE_XML}):
            self.Document._cron_fetch_xml(batch_size=1)
        # Oldest reception first
        self.assertEqual(self.documents.mapped('xml_state'), ['done', 'pending', 'pending'])

    def test_transient_error_retries_then_fails(self):
        document = self.documents[0]
        error = {'status': 'error', 'transient': True, 'message': 'timeout'}
        with self._patch_fetch(error):
            for attempt in range(1, XML_MAX_ATTEMPTS):
                self._process(document)
                self.assertEqual(document.xml_state, 'pending')
                self.assertEqual(document.xml_attempts, attempt)
            self._process(document)
        self.assertEqual(document.xml_state, 'error')
        self.assertEqual(document.xml_query_error_message, 'timeout')
        self.assertEqual(self.sync.xml_state, 'error')

    def test_permanent_error(self):
        document = self.documents[0]
        with self._patch_fetch({'status': 'error', 'transient': False, 'message': 'Código: 66'}):
            self._process(document)
        self.assertEqual(document.xml_state, 'error')

    def test_unsupported_xml_is_error(self):
        document = self.documents[0]
        with self._patch_fetch({'status': 'success', 'xml_content': b'<Other/>'}):
            self._process(document)
        self.assertEqual(document.xml_state, 'error')

    def test_company_without_direct_einvoicing_is_skipped(self):
        self.company.type_einvoicing = 'no'
        with self._patch_fetch({'status': 'success', 'xml_content': INVOICE_XML}) as fetch:
            self.Document._cron_fetch_xml(batch_size=10)
        fetch.assert_not_called()
        self.assertEqual(set(self.documents.mapped('xml_state')), {'pending'})

    def test_not_processing_anymore_is_skipped(self):
        document = self.documents[0]
        document.xml_state = 'done'
        with self._patch_fetch({'status': 'error', 'transient': False, 'message': 'x'}):
            document._xml_process()
        self.assertEqual(document.xml_state, 'done')

    def test_stale_processing_released(self):
        stale, recent = self.documents[0], self.documents[1]
        stale.write({
            'xml_state': 'processing',
            'xml_processing_since': fields.Datetime.now() - timedelta(minutes=XML_STALE_MINUTES + 1),
        })
        recent.write({'xml_state': 'processing', 'xml_processing_since': fields.Datetime.now()})
        self.Document._xml_release_stale()
        self.assertEqual(stale.xml_state, 'pending')
        self.assertEqual(recent.xml_state, 'processing')

    def test_wizard_skips_processing_and_done(self):
        processing, done, failed = self.documents
        processing.write({'xml_state': 'processing', 'xml_processing_since': fields.Datetime.now()})
        done.xml_state = 'done'
        failed.write({'xml_state': 'error', 'xml_attempts': XML_MAX_ATTEMPTS})
        wizard = self.env['dian.document.xml.fetch.wizard'].with_context(
            active_model='dian.document', active_ids=self.documents.ids).create({})
        self.assertEqual(wizard.to_queue_count, 1)
        self.assertEqual(wizard.processing_count, 1)
        self.assertEqual(wizard.done_count, 1)
        wizard.action_confirm()
        self.assertEqual(processing.xml_state, 'processing')
        self.assertEqual(done.xml_state, 'done')
        self.assertEqual(failed.xml_state, 'pending')
        self.assertEqual(failed.xml_attempts, 0)
        self.assertTrue(failed.xml_priority)
        # Requested documents go first
        claimed = self.Document._xml_claim(1)
        self.assertEqual(claimed, failed)
        self.assertEqual(failed.xml_state, 'processing')
