# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from unittest.mock import patch

import anthropic
import httpx2

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.ai_anthropic.utils import llm_api_service

UBL_NS = (
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'
)
SENDER_VAT = '900123456'
RECEIVER_VAT = '800111222'


def invoice_xml(number='FE-1', quantity=2.0, price=100000.0, percent=15.0, tax_levels='', order='', payable=None):
    subtotal = quantity * price
    tax = subtotal * percent / 100
    payable = subtotal + tax if payable is None else payable
    return f"""<?xml version="1.0"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" {UBL_NS}>
  <cbc:IssueDate>2026-11-01</cbc:IssueDate>
  <cbc:DueDate>2026-12-15</cbc:DueDate>
  <cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
  <cac:OrderReference><cbc:ID>{order}</cbc:ID></cac:OrderReference>
  <cac:AccountingSupplierParty><cac:Party><cac:PartyTaxScheme>
    <cbc:CompanyID schemeName="31">{SENDER_VAT}</cbc:CompanyID>
    <cbc:TaxLevelCode>{tax_levels}</cbc:TaxLevelCode>
  </cac:PartyTaxScheme></cac:Party></cac:AccountingSupplierParty>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount>{subtotal}</cbc:LineExtensionAmount>
    <cbc:PayableAmount>{payable}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="94">{quantity}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount>{subtotal}</cbc:LineExtensionAmount>
    <cac:TaxTotal>
      <cbc:TaxAmount>{tax}</cbc:TaxAmount>
      <cac:TaxSubtotal>
        <cbc:TaxableAmount>{subtotal}</cbc:TaxableAmount>
        <cbc:TaxAmount>{tax}</cbc:TaxAmount>
        <cac:TaxCategory><cbc:Percent>{percent}</cbc:Percent>
          <cac:TaxScheme><cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme>
        </cac:TaxCategory>
      </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:Item><cbc:Description>Servicio de prueba</cbc:Description></cac:Item>
    <cac:Price><cbc:PriceAmount>{price}</cbc:PriceAmount><cbc:BaseQuantity>1</cbc:BaseQuantity></cac:Price>
  </cac:InvoiceLine>
</Invoice>""".encode()


def credit_note_xml(reference, cufe=''):
    return f"""<?xml version="1.0"?>
<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" {UBL_NS}>
  <cbc:IssueDate>2026-11-02</cbc:IssueDate>
  <cbc:CreditNoteTypeCode>91</cbc:CreditNoteTypeCode>
  <cac:DiscrepancyResponse><cbc:ReferenceID>{reference}</cbc:ReferenceID><cbc:ResponseCode>2</cbc:ResponseCode></cac:DiscrepancyResponse>
  <cac:BillingReference><cac:InvoiceDocumentReference>
    <cbc:ID>{reference}</cbc:ID><cbc:UUID>{cufe}</cbc:UUID>
  </cac:InvoiceDocumentReference></cac:BillingReference>
  <cac:AccountingSupplierParty><cac:Party><cac:PartyTaxScheme>
    <cbc:CompanyID schemeName="31">{SENDER_VAT}</cbc:CompanyID>
  </cac:PartyTaxScheme></cac:Party></cac:AccountingSupplierParty>
  <cac:LegalMonetaryTotal><cbc:PayableAmount>100</cbc:PayableAmount></cac:LegalMonetaryTotal>
</CreditNote>""".encode()


def tool_step(name, **arguments):
    return (name, arguments)


READ_AND_CREATE = [
    tool_step('dian_ai_tool_get_document'),
    tool_step('dian_ai_tool_create_bill'),
    tool_step('dian_ai_tool_compare'),
    tool_step('dian_ai_tool_review_taxes'),
]


def finish_step(confidence=0.95):
    return tool_step('dian_ai_tool_finish', confidence=confidence, explanation='IVA según el producto.',
                     __end_message='Listo')


@tagged('post_install', '-at_install')
class TestDianInvoiceAgent(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data_2 = cls.setup_other_company()
        cls.company = cls.company_data['company']
        cls.company.vat = RECEIVER_VAT
        if 'pr_approval_po' in cls.company._fields:
            cls.company.pr_approval_po = False
        cls.user = new_test_user(
            cls.env, login='dian_agent_user',
            groups='account.group_account_manager,purchase.group_purchase_manager',
            company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)],
        )
        cls.tax = cls.company_data['default_tax_purchase']
        cls.withholding = cls.env['account.tax'].create({
            'name': 'ReteFuente prueba', 'amount': -2.5, 'type_tax_use': 'purchase',
            'company_id': cls.company.id,
        })
        cls.vendor = cls.env['res.partner'].create({'name': 'Proveedor prueba', 'vat': SENDER_VAT})
        cls.product = cls.env['product.product'].create({
            'name': 'Servicio de prueba', 'type': 'service', 'purchase_method': 'purchase',
            'supplier_taxes_id': [(6, 0, cls.tax.ids)],
        })
        cls.config = cls.env['dian.ai.config'].create({
            'company_id': cls.company.id,
            'enabled': True,
            'mode': 'post',
            'user_id': cls.user.id,
            'start_date': fields.Date.today() - timedelta(days=5),
        })

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('ai.anthropic_key', 'test-key')
        self.script = []
        self.requests = []
        self.events = []

        def handler(request):
            self.requests.append(json.loads(request.content))
            if not self.script:
                return httpx2.Response(200, json=self._api_message([{'type': 'text', 'text': 'Fin'}], 'end_turn'))
            step = self.script.pop(0)
            if isinstance(step, int):
                return httpx2.Response(step, json={
                    'type': 'error', 'error': {'type': 'api_error', 'message': 'API caída'},
                })
            name, arguments = step
            arguments = arguments() if callable(arguments) else arguments
            return httpx2.Response(200, json=self._api_message(
                [{'type': 'tool_use', 'id': f'call_{len(self.requests)}', 'name': name, 'input': arguments}],
                'tool_use',
            ))

        def get_client(api_key):
            return anthropic.Anthropic(
                api_key=api_key, max_retries=0,
                http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
            )

        document_class = type(self.env['dian.document'])

        def send_event(document, event):
            self.events.append((document.id, event))
            document.ie_event_display = event

        for target, attribute, replacement in (
            (llm_api_service, '_get_client', get_client),
            (document_class, '_ereignis_senden', send_event),
            (document_class, 'zustand_prufen', lambda document, notif=True: None),
        ):
            patcher = patch.object(target, attribute, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def _api_message(content, stop_reason):
        return {
            'id': 'msg_1', 'type': 'message', 'role': 'assistant', 'model': 'claude-opus-5-5',
            'content': content, 'stop_reason': stop_reason, 'stop_sequence': None,
            'usage': {'input_tokens': 100, 'output_tokens': 10, 'cache_read_input_tokens': 40},
        }

    def _make_order(self, quantity=2.0, price=100000.0, confirm=True, product=None):
        order = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'product_id': (product or self.product).id,
                'product_qty': quantity,
                'price_unit': price,
                'tax_ids': [(6, 0, self.tax.ids)],
            })],
        })
        if confirm:
            order.button_confirm()
        return order

    def _make_document(self, order=None, xml=None, number='FE-1', reception=None, **vals):
        Document = self.env['dian.document'].with_company(self.company)
        xml = xml or invoice_xml(number=number, order=order.name if order else '')
        return Document.create({
            'company_id': self.company.id,
            'cufe': f'cufe-{number}',
            'name': number,
            'reception': reception or fields.Datetime.now(),
            'sender_vat': SENDER_VAT,
            'receiver_vat': RECEIVER_VAT,
            'xml_state': 'done',
            'purchase_id': order.id if order else False,
            **Document._xml_vals_from_content(xml),
            **vals,
        })

    def _run_agent(self, script):
        self.script = list(script)
        self.env['dian.document']._cron_ai_process()

    # ── Selección de documentos (CA-01) ──────────────────────────────────────

    def test_xml_extras_are_parsed(self):
        document = self._make_document(xml=invoice_xml(tax_levels='O-13;O-15'))
        self.assertEqual(fields.Date.to_string(document.xml_issue_date), '2026-11-01')
        self.assertEqual(fields.Date.to_string(document.xml_due_date), '2026-12-15')
        self.assertEqual(document.xml_tax_level_codes, 'O-13;O-15')

    def test_classification(self):
        approved = self._make_document(self._make_order(), number='OK')
        no_order = self._make_document(number='NO-OC')
        draft_order = self._make_document(self._make_order(confirm=False), number='BORRADOR')
        pending = self._make_document(self._make_order(), number='PEND', xml_state='pending')
        failed = self._make_document(self._make_order(), number='ERR', xml_state='error')
        (approved | no_order | draft_order | pending | failed)._ai_classify()
        self.assertEqual(approved.ai_state, 'inbox')
        self.assertEqual(no_order.ai_exception_code, 'no_purchase')
        self.assertEqual(draft_order.ai_exception_code, 'po_not_approved')
        self.assertEqual(pending.ai_exception_code, 'xml_pending')
        self.assertEqual(failed.ai_exception_code, 'xml_error')

    def test_approval_matrix_is_required(self):
        if 'pr_approval_po' not in self.company._fields:
            self.skipTest('purchase_approval no está instalado')
        document = self._make_document(self._make_order())
        self.company.pr_approval_po = True
        document.purchase_id.approval_status = 'pending'
        document._ai_classify()
        self.assertEqual(document.ai_exception_code, 'po_not_approved')

    def test_order_is_linked_by_reference(self):
        order = self._make_order()
        document = self._make_document(xml=invoice_xml(order=order.name))
        document._ai_classify()
        self.assertEqual(document.purchase_id, order)
        self.assertEqual(document.ai_state, 'inbox')

    def test_documents_before_start_date_are_ignored(self):
        document = self._make_document(
            self._make_order(), reception=fields.Datetime.now() - timedelta(days=30))
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertFalse(document.ai_state)
        self.assertFalse(document.move_id)
        self.assertFalse(self.events)

    def test_disabled_company_is_not_processed(self):
        self.config.enabled = False
        document = self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertFalse(document.ai_state)
        self.assertFalse(self.requests)

    # ── Causación (CA-02, CA-03, CA-06) ──────────────────────────────────────

    def test_bill_is_created_from_order_and_posted(self):
        order = self._make_order()
        document = self._make_document(order)
        self._run_agent(READ_AND_CREATE + [finish_step()])
        move = document.move_id
        self.assertEqual(document.ai_state, 'posted')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move, order.invoice_ids)
        self.assertEqual(move.ref, 'FE-1')
        self.assertEqual(move.uuid_ei_ref, 'cufe-FE-1')
        self.assertEqual(fields.Date.to_string(move.invoice_date), '2026-11-01')
        self.assertEqual(fields.Date.to_string(move.invoice_date_due), '2026-12-15')
        self.assertIn('IVA según el producto.', move.ai_explanation)
        run = document.ai_run_ids
        self.assertEqual(run.outcome, 'posted')
        self.assertEqual(run.input_tokens, 500)
        self.assertEqual(run.cached_tokens, 200)
        self.assertEqual(run.llm_model, 'claude-opus-5-5')

    def test_system_prompt_and_tools_reach_the_model(self):
        self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        body = self.requests[0]
        self.assertIn('auxiliar contable', body['system'])
        self.assertEqual(body['model'], 'claude-opus-5-5')
        names = {tool['name'] for tool in body['tools']}
        self.assertEqual(names, {
            'dian_ai_tool_get_document', 'dian_ai_tool_create_bill', 'dian_ai_tool_compare',
            'dian_ai_tool_review_taxes', 'dian_ai_tool_adjust_tax', 'dian_ai_tool_finish',
            'dian_ai_tool_propose_claim',
        })

    def test_tool_results_contain_document_data(self):
        self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        result = self.requests[1]['messages'][-1]['content'][0]['content']
        self.assertIn('Servicio de prueba', result)
        self.assertNotIn('An error occurred', json.dumps(self.requests[-1]['messages']))

    def test_draft_mode_leaves_bill_ready(self):
        self.config.mode = 'draft'
        document = self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertEqual(document.ai_state, 'draft')
        self.assertEqual(document.move_id.state, 'draft')

    def test_difference_over_tolerance_leaves_draft(self):
        order = self._make_order(price=100000.0)
        document = self._make_document(order, xml=invoice_xml(price=120000.0, order=order.name))
        self._run_agent(READ_AND_CREATE + [finish_step(confidence=1.0)])
        self.assertEqual(document.ai_state, 'draft')
        self.assertEqual(document.move_id.state, 'draft')
        self.assertIn('unit_price', document.ai_detail)
        self.assertIn('unit_price', ''.join(document.move_id.message_ids.mapped('body')))
        self.assertTrue(document.move_id.activity_ids)

    def test_difference_within_tolerance_is_posted(self):
        order = self._make_order(price=100000.0)
        document = self._make_document(order, xml=invoice_xml(price=100000.0, payable=230050.0, order=order.name))
        self.config.total_tolerance_percent = 0.1
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertEqual(document.ai_state, 'posted')

    def test_wrong_vat_tax_leaves_draft(self):
        order = self._make_order()
        document = self._make_document(order, xml=invoice_xml(percent=19.0, order=order.name))
        self._run_agent(READ_AND_CREATE + [finish_step(confidence=1.0)])
        self.assertEqual(document.ai_state, 'draft')
        self.assertIn('tax', document.ai_detail)

    def test_low_confidence_leaves_draft(self):
        document = self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step(confidence=0.5)])
        self.assertEqual(document.ai_state, 'draft')
        self.assertIn('umbral', document.ai_detail)

    def test_model_cannot_post_without_compare_or_review_steps(self):
        """Skipping tools does not skip the checks: finish repeats them in code."""
        order = self._make_order(price=100000.0)
        document = self._make_document(order, xml=invoice_xml(price=120000.0, order=order.name))
        self._run_agent([tool_step('dian_ai_tool_create_bill'), finish_step(confidence=1.0)])
        self.assertEqual(document.move_id.state, 'draft')

    def test_probable_duplicate_leaves_draft(self):
        first = self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertEqual(first.ai_state, 'posted')
        second = self._make_document(self._make_order(), number='FE-2')
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertEqual(second.ai_state, 'draft')
        self.assertIn('duplicada', second.ai_detail)

    def test_running_twice_does_not_duplicate(self):
        order = self._make_order()
        document = self._make_document(order)
        self._run_agent(READ_AND_CREATE + [finish_step()])
        move = document.move_id
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertEqual(document.move_id, move)
        self.assertEqual(len(order.invoice_ids), 1)
        self.assertEqual(len(document.ai_run_ids), 1)

    def test_create_bill_tool_is_idempotent(self):
        order = self._make_order()
        document = self._make_document(order)
        self._run_agent([
            tool_step('dian_ai_tool_create_bill'), tool_step('dian_ai_tool_create_bill'), finish_step(),
        ])
        self.assertEqual(len(order.invoice_ids), 1)
        self.assertEqual(document.ai_state, 'posted')

    def test_existing_invoice_with_same_cufe_is_linked_and_not_processed(self):
        order = self._make_order()
        document = self._make_document(order)
        existing = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.vendor.id, 'company_id': self.company.id,
            'uuid_ei_ref': document.cufe,
        })
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertEqual(document.move_id, existing)
        self.assertFalse(order.invoice_ids)
        self.assertFalse(self.requests)

    def test_nothing_to_invoice_goes_to_exceptions(self):
        product = self.env['product.product'].create({
            'name': 'Servicio recibido', 'type': 'service', 'purchase_method': 'receive',
        })
        order = self._make_order(product=product)
        document = self._make_document(order)
        with patch.object(type(order), 'action_create_invoice',
                          side_effect=UserError('No hay líneas por facturar')):
            self._run_agent([tool_step('dian_ai_tool_create_bill')])
        self.assertEqual(document.ai_state, 'exception')
        self.assertEqual(document.ai_exception_code, 'not_invoiceable')
        self.assertEqual(document.ai_run_ids.outcome, 'exception')

    def test_agent_stopping_early_leaves_draft(self):
        document = self._make_document(self._make_order())
        self._run_agent([tool_step('dian_ai_tool_create_bill')])
        self.assertEqual(document.ai_state, 'draft')
        self.assertEqual(document.move_id.state, 'draft')

    # ── Fallas ───────────────────────────────────────────────────────────────

    def test_api_failure_retries_then_error(self):
        document = self._make_document(self._make_order())
        self._run_agent([500])
        self.assertEqual(document.ai_state, 'inbox')
        self.assertEqual(document.ai_attempts, 1)
        self.assertEqual(document.ai_run_ids.outcome, 'error')
        self._run_agent([500])
        self._run_agent([500])
        self.assertEqual(document.ai_state, 'error')
        self.assertEqual(document.ai_attempts, 3)
        self.assertTrue(document.activity_ids)
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertEqual(len(document.ai_run_ids), 3)

    def test_tool_error_is_returned_to_the_model(self):
        document = self._make_document(self._make_order())
        self._run_agent([tool_step('dian_ai_tool_compare')] + READ_AND_CREATE + [finish_step()])
        self.assertIn('Primero debe crear la factura', json.dumps(self.requests[1]['messages']))
        self.assertEqual(document.ai_state, 'posted')

    # ── Impuestos (CA-04, CA-04b, CA-05) ─────────────────────────────────────

    def _adjust_step(self, document, rule=None):
        def arguments():
            return {
                'line_id': document.move_id.invoice_line_ids[0].id,
                'tax_id': self.withholding.id,
                'operation': 'add',
                'reason': 'Falta la ReteFuente según la posición fiscal.',
                'rule_id': rule.id if rule else 0,
            }
        return ('dian_ai_tool_adjust_tax', arguments)

    def test_review_taxes_reports_missing_tax(self):
        self.product.supplier_taxes_id = [(4, self.withholding.id)]
        document = self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertIn(self.withholding.name, json.dumps(self.requests[4]['messages'], ensure_ascii=False))
        self.assertTrue(document.ai_compare_result)

    def test_adjusted_tax_leaves_draft_by_default(self):
        document = self._make_document(self._make_order())
        self._run_agent([tool_step('dian_ai_tool_create_bill'), self._adjust_step(document), finish_step()])
        move = document.move_id
        self.assertEqual(document.ai_state, 'draft')
        self.assertEqual(move.state, 'draft')
        self.assertEqual(move.ai_review_state, 'pending')
        self.assertIn(self.withholding, move.invoice_line_ids.tax_ids)
        # 200.000 base + 15 % IVA - 2,5 % ReteFuente: Odoo computes it
        self.assertAlmostEqual(move.amount_total, 225000.0)

    def test_adjusted_tax_is_posted_for_review_and_learned(self):
        self.config.post_with_tax_adjustment = True
        document = self._make_document(self._make_order())
        self._run_agent([tool_step('dian_ai_tool_create_bill'), self._adjust_step(document), finish_step()])
        move = document.move_id
        self.assertEqual(document.ai_state, 'review')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.ai_review_state, 'pending')
        self.assertTrue(move.activity_ids.filtered(lambda a: 'Para revisión' in a.summary))
        rule = self.env['dian.ai.rule'].search([('move_id', '=', move.id)])
        self.assertEqual(rule.state, 'proposed')

        move.with_user(self.user).action_ai_review_confirm()
        self.assertEqual(rule.state, 'learned')
        self.assertEqual(move.ai_review_state, 'confirmed')
        self.assertEqual(document.ai_state, 'posted')

        # A learned rule no longer needs review, even with the setting off
        self.config.post_with_tax_adjustment = False
        # Another amount: same vendor, date and amount would be a probable duplicate
        order = self._make_order(price=150000.0)
        second = self._make_document(order, number='FE-2', xml=invoice_xml(price=150000.0, order=order.name))
        self._run_agent([
            tool_step('dian_ai_tool_create_bill'), self._adjust_step(second, rule), finish_step(),
        ])
        self.assertEqual(second.ai_state, 'posted', second.ai_detail)
        self.assertFalse(second.move_id.ai_review_state)

    def test_unrelated_rule_does_not_avoid_review(self):
        rule = self.env['dian.ai.rule'].create({
            'company_id': self.company.id, 'scope': 'partner', 'partner_id': self.partner_a.id,
            'operation': 'add', 'tax_id': self.withholding.id,
        })
        document = self._make_document(self._make_order())
        self._run_agent([tool_step('dian_ai_tool_create_bill'), self._adjust_step(document, rule), finish_step()])
        self.assertEqual(document.move_id.ai_review_state, 'pending')

    def test_foreign_tax_or_line_is_rejected(self):
        document = self._make_document(self._make_order())
        foreign_tax = self.env['account.tax'].create({
            'name': 'Venta', 'amount': 10, 'type_tax_use': 'sale', 'company_id': self.company.id,
        })

        def arguments():
            return {'line_id': document.move_id.invoice_line_ids[0].id, 'tax_id': foreign_tax.id,
                    'operation': 'add', 'reason': 'x', 'rule_id': 0}

        self._run_agent([tool_step('dian_ai_tool_create_bill'), ('dian_ai_tool_adjust_tax', arguments), finish_step()])
        self.assertNotIn(foreign_tax, document.move_id.invoice_line_ids.tax_ids)
        self.assertEqual(document.ai_state, 'posted')

    def test_responsibilities_mismatch_leaves_draft_and_proposes_fix(self):
        order = self._make_order()
        document = self._make_document(order, xml=invoice_xml(tax_levels='O-13', order=order.name))
        self._run_agent(READ_AND_CREATE + [finish_step(confidence=1.0)])
        self.assertEqual(document.ai_state, 'draft')
        self.assertIn('O-13', document.ai_detail)
        self.assertTrue(document.activity_ids.filtered(lambda a: 'responsabilidades' in a.summary))

    # ── Aprendizaje (CA-07, CA-07b) ──────────────────────────────────────────

    def test_accountant_correction_is_registered(self):
        self.config.mode = 'draft'
        document = self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        line = document.move_id.invoice_line_ids[0]
        line.with_user(self.user).tax_ids = [(4, self.withholding.id)]
        rule = self.env['dian.ai.rule'].search([('move_id', '=', document.move_id.id)])
        self.assertEqual(rule.origin, 'correction')
        self.assertEqual(rule.operation, 'add')
        self.assertEqual(rule.tax_id, self.withholding)
        self.assertEqual(rule.state, 'learned')
        self.assertEqual(rule.user_id, self.user)
        self.assertIn(rule, self.env['dian.ai.rule']._ai_applicable(self.company, self.vendor, self.product))

    def test_agent_changes_are_not_corrections(self):
        document = self._make_document(self._make_order())
        self._run_agent([tool_step('dian_ai_tool_create_bill'), self._adjust_step(document), finish_step()])
        rules = self.env['dian.ai.rule'].search([('move_id', '=', document.move_id.id)])
        self.assertEqual(rules.mapped('origin'), ['agent'])

    def test_correcting_pending_review_rejects_proposal(self):
        self.config.mode = 'draft'
        document = self._make_document(self._make_order())
        self._run_agent([tool_step('dian_ai_tool_create_bill'), self._adjust_step(document), finish_step()])
        move = document.move_id
        move.invoice_line_ids[0].with_user(self.user).tax_ids = [(3, self.withholding.id)]
        self.assertEqual(move.ai_review_state, 'corrected')
        proposal = self.env['dian.ai.rule'].with_context(active_test=False).search(
            [('move_id', '=', move.id), ('origin', '=', 'agent')])
        self.assertEqual(proposal.state, 'rejected')

    def test_explain_to_agent_creates_rule_with_scope(self):
        self.config.mode = 'draft'
        document = self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        wizard = self.env['dian.ai.explain.wizard'].with_user(self.user).create({
            'move_id': document.move_id.id,
            'explanation': 'A este proveedor no se le practica ReteIVA.',
            'scope': 'partner',
            'operation': 'remove',
            'tax_id': self.withholding.id,
        })
        wizard.action_confirm()
        rule = self.env['dian.ai.rule'].search([('origin', '=', 'explanation')])
        self.assertEqual(rule.partner_id, self.vendor)
        self.assertIn(rule, self.env['dian.ai.rule']._ai_applicable(self.company, self.vendor, self.product))
        rule.active = False
        self.assertNotIn(rule, self.env['dian.ai.rule']._ai_applicable(self.company, self.vendor, self.product))

    # ── Eventos (CA-08) ──────────────────────────────────────────────────────

    def test_events_follow_order_and_wait_for_reception(self):
        order = self._make_order()
        document = self._make_document(order)
        self._run_agent(READ_AND_CREATE + [finish_step()])
        self.assertEqual(self.events, [(document.id, '030')])

        # 032 needs the quantities received
        self._run_agent([])
        self.assertEqual(len(self.events), 1)
        order.order_line.qty_received = 2.0
        self._run_agent([])
        self.assertEqual(self.events[-1], (document.id, '032'))

        # 033 waits for approval while it is not automatic
        self._run_agent([])
        self.assertEqual(len(self.events), 2)
        self.assertTrue(document.activity_ids.filtered(lambda a: '033' in a.summary))

        self.config.auto_event_033 = True
        self._run_agent([])
        self.assertEqual(self.events[-1], (document.id, '033'))
        self._run_agent([])
        self.assertEqual(len(self.events), 3)

    def test_event_already_registered_is_not_repeated(self):
        document = self._make_document(self._make_order())
        document_class = type(document)

        def status(doc, notif=True):
            doc.ie_event_display = '032'

        with patch.object(document_class, 'zustand_prufen', status):
            self.assertFalse(document._ai_send_event('030'))
        self.assertFalse(self.events)

    def test_acknowledgment_also_goes_for_exceptions(self):
        document = self._make_document(number='SIN-OC')
        self._run_agent([])
        self.assertEqual(document.ai_state, 'exception')
        self.assertEqual(self.events, [(document.id, '030')])

    def test_document_for_other_company_gets_no_event(self):
        self._make_document(number='OTRO', receiver_vat='111111111')
        self._run_agent([])
        self.assertFalse(self.events)

    def test_claim_is_only_proposed(self):
        document = self._make_document(self._make_order())
        self._run_agent([
            tool_step('dian_ai_tool_propose_claim', claim_code='01', reason='Precio distinto'),
            tool_step('dian_ai_tool_propose_claim', claim_code='99', reason='Inventado'),
            tool_step('dian_ai_tool_create_bill'),
            finish_step(),
        ])
        self.assertEqual(document.ie_claim_id.dian_code, '01')
        self.assertTrue(document.activity_ids.filtered(lambda a: '031' in a.summary))
        self.assertIn('no existe', json.dumps(self.requests[2]['messages']))
        self.assertNotIn('031', [event for __, event in self.events])

    def test_tacit_acceptance_alert(self):
        document = self._make_document(
            self._make_order(confirm=False), reception=fields.Datetime.now() - timedelta(days=5))
        self._run_agent([])
        self.assertTrue(document.activity_ids.filtered(lambda a: 'próximo a vencer' in a.summary))
        self.assertTrue(document.ai_tacit_alert_sent)

    # ── Notas crédito y débito (CA-11) ───────────────────────────────────────

    def test_note_is_not_posted_and_warns_invoice(self):
        order = self._make_order()
        invoice = self._make_document(order)
        self._run_agent(READ_AND_CREATE + [finish_step()])
        note = self._make_document(xml=credit_note_xml('FE-1', invoice.cufe), number='NC-1')
        self._run_agent([])
        self.assertEqual(note.ai_state, 'note_alert')
        self.assertFalse(note.move_id)
        self.assertTrue(note.activity_ids)
        self.assertTrue(invoice.move_id.activity_ids.filtered(lambda a: 'nota' in a.summary.lower()))
        self.assertTrue(invoice.move_id.ai_has_pending_note)
        note.with_user(self.user).action_ai_note_reviewed()
        self.assertEqual(note.ai_state, 'note_reviewed')

    def test_pending_note_keeps_invoice_in_draft(self):
        order = self._make_order()
        self._make_document(xml=credit_note_xml('FE-1'), number='NC-1')
        invoice = self._make_document(order)
        self._run_agent(READ_AND_CREATE + [finish_step(confidence=1.0)])
        self.assertEqual(invoice.ai_state, 'draft')
        self.assertIn('notas pendientes', invoice.ai_detail)

    # ── Trazabilidad y seguridad (CA-09, CA-10, CA-12) ───────────────────────

    def test_audit_trail_on_chatter(self):
        document = self._make_document(self._make_order())
        self._run_agent(READ_AND_CREATE + [finish_step()])
        body = ''.join(document.message_ids.mapped('body'))
        for expected in ('_ai_tool_create_bill', 'Modelo de IA', 'claude-opus-5-5', self.user.name,
                         'Datos de entrada', 'Resultado'):
            self.assertIn(expected, body)
        self.assertIn('_ai_tool_finish', ''.join(document.move_id.message_ids.mapped('body')))

    def test_tools_require_accounting_manager(self):
        document = self._make_document(self._make_order())
        plain_user = new_test_user(
            self.env, login='dian_no_access', groups='base.group_user',
            company_id=self.company.id, company_ids=[(6, 0, self.company.ids)],
        )
        Document = self.env['dian.document'].with_user(plain_user).with_context(dian_ai_document_id=document.id)
        with self.assertRaises(AccessError):
            Document._ai_tool_compare()
        with self.assertRaises(UserError):
            document.with_user(plain_user).action_ai_process()

    def test_tools_only_work_inside_a_run(self):
        with self.assertRaises(UserError):
            self.env['dian.document'].with_user(self.user)._ai_tool_compare()

    def test_responsible_user_must_be_accounting_manager(self):
        plain_user = new_test_user(
            self.env, login='dian_plain', groups='base.group_user',
            company_id=self.company.id, company_ids=[(6, 0, self.company.ids)],
        )
        with self.assertRaises(ValidationError):
            self.config.user_id = plain_user

    def test_user_without_company_access_cannot_read_other_company(self):
        other = self.company_data_2['company']
        document = self.env['dian.document'].sudo().create({
            'company_id': other.id, 'cufe': 'cufe-b', 'name': 'B-1',
            'reception': fields.Datetime.now(), 'xml_state': 'done', 'invoice_type': '01',
        })
        Document = self.env['dian.document'].with_user(self.user)
        self.assertFalse(Document.search([('id', '=', document.id)]))
        with self.assertRaises(AccessError):
            Document.with_context(dian_ai_document_id=document.id)._ai_tool_compare()

    def test_company_rules_and_runs_are_isolated(self):
        other = self.company_data_2['company']
        other.vat = '700222333'
        foreign_rule = self.env['dian.ai.rule'].sudo().create({
            'company_id': other.id, 'scope': 'company', 'explanation': 'Solo B',
        })
        self.assertNotIn(
            foreign_rule, self.env['dian.ai.rule']._ai_applicable(self.company, self.vendor, self.product))
        self.assertFalse(self.env['dian.ai.rule'].with_user(self.user).search([('id', '=', foreign_rule.id)]))
        document_b = self.env['dian.document'].sudo().create({
            'company_id': other.id, 'cufe': 'cufe-b', 'name': 'B-1', 'receiver_vat': '700222333',
            'reception': fields.Datetime.now(), 'xml_state': 'done', 'invoice_type': '01',
        })
        self._run_agent([])
        self.assertFalse(document_b.ai_state)
