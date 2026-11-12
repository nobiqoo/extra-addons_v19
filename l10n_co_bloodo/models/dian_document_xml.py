# -*- coding: utf-8 -*-
"""
XML data of dian.document (received documents synchronized by
l10n_co_dian_invoice_synchronizer).

The DIAN catalog blocks the automated ZIP download (Cloudflare Turnstile), so the
XML is fetched here through the GetXmlByDocumentKey web service, signed with the
company certificate. Both the fields filled from the XML and the logic that fetches
and parses it live in this module.

Fetching is done only by the cron "DIAN: Obtener XML de documentos recibidos"
(_cron_fetch_xml). The request wizard (dian.document.xml.fetch.wizard) only marks
documents as prioritary and triggers the cron, so there is always a single
consumer. Documents are claimed with SELECT ... FOR UPDATE SKIP LOCKED and moved to
'processing' (committed) before calling DIAN, which is what keeps the wizard from
queueing documents the cron is processing.
"""
import logging
from base64 import b64decode
from datetime import timedelta
import xml.etree.ElementTree as ET

from odoo import _, api, fields, models, modules

_logger = logging.getLogger(__name__)

# UBL 2.1 namespaces (DIAN Colombia)
NS = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}



def _text(el):
    """Return element text stripped or None if el is None."""
    if el is None:
        return None
    return (el.text or '').strip() or None


def _float(text_val):
    """Parse float from string; return 0.0 if invalid or None."""
    if text_val is None:
        return 0.0
    try:
        return float(text_val.replace(',', '.'))
    except (ValueError, TypeError):
        return 0.0


def _unwrap_attached_document(xml_content):
    """
    If xml_content is a DIAN AttachedDocument, return the embedded Invoice /
    CreditNote / DebitNote (cac:Attachment/cac:ExternalReference/cbc:Description).
    Otherwise return xml_content unchanged.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return xml_content
    if root.tag.split('}')[-1] != 'AttachedDocument':
        return xml_content
    description = root.find('.//cac:Attachment/cac:ExternalReference/cbc:Description', NS)
    text = _text(description)
    return text.encode('utf-8') if text else xml_content


def _root_tag(xml_content):
    """Local name of the root element, or False if xml_content is not valid XML."""
    try:
        return ET.fromstring(xml_content).tag.split('}')[-1]
    except ET.ParseError:
        return False


def _extract_dian_validation_result(xml_content):
    """
    From a DIAN AttachedDocument, return the text of the validation the DIAN gave
    the issuer (embedded ApplicationResponse: cac:DocumentResponse/cac:Response/
    cbc:Description). Many technology providers embed it there. False otherwise.
    """
    if _root_tag(xml_content) != 'AttachedDocument':
        return False
    root = ET.fromstring(xml_content)
    for description in root.findall('.//cac:Attachment/cac:ExternalReference/cbc:Description', NS):
        text = _text(description)
        if not text:
            continue
        try:
            embedded = ET.fromstring(text.encode('utf-8'))
        except ET.ParseError:
            continue
        if embedded.tag.split('}')[-1] != 'ApplicationResponse':
            continue
        response = _text(embedded.find('cac:DocumentResponse/cac:Response/cbc:Description', NS))
        if response:
            return response
    return False


def _summarize_taxes(tax_total_commands):
    """
    Portal-like tax summary (tax_amount_5_percent, _19_percent, _iva, _ica, _ipc)
    computed from the document-level tax_total_ids commands of the XML.
    """
    summary = {
        'tax_amount_5_percent': 0.0,
        'tax_amount_19_percent': 0.0,
        'tax_amount_iva': 0.0,
        'tax_amount_ica': 0.0,
        'tax_amount_ipc': 0.0,
    }
    for command in tax_total_commands or []:
        if not (isinstance(command, (list, tuple)) and len(command) == 3):
            continue
        vals = command[2] or {}
        amount = vals.get('tax_amount') or 0.0
        percent = vals.get('percent') or 0.0
        scheme_name = (vals.get('tax_scheme_name') or '').upper()
        if 'IVA' in scheme_name:
            summary['tax_amount_iva'] += amount
        elif 'ICA' in scheme_name:
            summary['tax_amount_ica'] += amount
        elif 'IPC' in scheme_name:
            summary['tax_amount_ipc'] += amount
        if percent == 19:
            summary['tax_amount_19_percent'] += amount
        elif percent == 5:
            summary['tax_amount_5_percent'] += amount
    return summary


def _parse_tax_subtotals(parent_el):
    """From a cac:TaxTotal element, yield one dict per cac:TaxSubtotal (for create vals)."""
    if parent_el is None:
        return
    for subtotal in parent_el.findall('cac:TaxSubtotal', NS):
        tax_amt = subtotal.find('cbc:TaxAmount', NS)
        taxable_amt = subtotal.find('cbc:TaxableAmount', NS)
        cat = subtotal.find('cac:TaxCategory', NS)
        percent_el = cat.find('cbc:Percent', NS) if cat is not None else None
        scheme = cat.find('cac:TaxScheme', NS) if cat is not None else None
        scheme_id = scheme.find('cbc:ID', NS) if scheme is not None else None
        scheme_name = scheme.find(
            'cbc:Name', NS) if scheme is not None else None
        yield {
            'tax_amount': _float(_text(tax_amt)),
            'taxable_amount': _float(_text(taxable_amt)),
            'percent': _float(_text(percent_el)),
            'tax_scheme_id': _text(scheme_id),
            'tax_scheme_name': _text(scheme_name),
        }


def _parse_tax_total(parent_el):
    """From a cac:TaxTotal element, build list of (0, 0, vals) for document or line."""
    if parent_el is None:
        return []
    tax_amt_el = parent_el.find('cbc:TaxAmount', NS)
    tax_amount = _float(_text(tax_amt_el))
    result = []
    for st in _parse_tax_subtotals(parent_el):
        st['tax_amount'] = st['tax_amount'] or tax_amount
        result.append((0, 0, st))
    if not result and tax_amount:
        result.append((0, 0, {
            'tax_amount': tax_amount,
            'taxable_amount': 0.0,
            'percent': 0.0,
            'tax_scheme_id': None,
            'tax_scheme_name': None,
        }))
    return result


def _parse_invoice_line(line_el, quantity_tag='cbc:InvoicedQuantity'):
    """
    From a cac:InvoiceLine element, build vals for dian.document.invoice.line (0, 0, vals).
    Also used for cac:DebitNoteLine, whose quantity is cbc:DebitedQuantity.
    """
    line_id_el = line_el.find('cbc:ID', NS)
    notes = []
    for note_el in line_el.findall('cbc:Note', NS):
        t = _text(note_el)
        if t:
            notes.append(t)
    qty_el = line_el.find(quantity_tag, NS)
    line_ext_el = line_el.find('cbc:LineExtensionAmount', NS)
    tax_total_el = line_el.find('cac:TaxTotal', NS)
    item_el = line_el.find('cac:Item', NS)
    desc_el = item_el.find(
        'cbc:Description', NS) if item_el is not None else None
    sellers_el = item_el.find(
        'cac:SellersItemIdentification/cbc:ID', NS) if item_el is not None else None
    if item_el is not None and sellers_el is None:
        sellers_el = item_el.find('cac:SellersItemIdentification', NS)
        if sellers_el is not None:
            sellers_el = sellers_el.find('cbc:ID', NS)
    standard_el = None
    if item_el is not None:
        standard_el = item_el.find('cac:StandardItemIdentification', NS)
        if standard_el is not None:
            standard_el = standard_el.find('cbc:ID', NS)
    price_el = line_el.find('cac:Price', NS)
    price_amt_el = price_el.find(
        'cbc:PriceAmount', NS) if price_el is not None else None
    base_qty_el = price_el.find(
        'cbc:BaseQuantity', NS) if price_el is not None else None

    line_vals = {
        'line_number': int(_float(_text(line_id_el))),
        'note': '\n'.join(notes) if notes else None,
        'invoiced_quantity': _float(_text(qty_el)),
        'quantity_unit_code': qty_el.get('unitCode') if qty_el is not None else None,
        'line_extension_amount': _float(_text(line_ext_el)),
        'tax_total_ids': _parse_tax_total(tax_total_el),
        'description': _text(desc_el),
        'sellers_item_identification': _text(sellers_el),
        'standard_item_identification': _text(standard_el),
        'price_amount': _float(_text(price_amt_el)),
        'base_quantity': _float(_text(base_qty_el)),
        'base_quantity_unit_code': base_qty_el.get('unitCode') if base_qty_el is not None else None,
    }
    return (0, 0, line_vals)


def _parse_credit_note_line(line_el):
    """From a cac:CreditNoteLine element, build vals for dian.document.invoice.line (0, 0, vals)."""
    line_id_el = line_el.find('cbc:ID', NS)
    notes = []
    for note_el in line_el.findall('cbc:Note', NS):
        t = _text(note_el)
        if t:
            notes.append(t)
    qty_el = line_el.find('cbc:CreditedQuantity', NS)
    credited_qty = _float(_text(qty_el))
    line_ext_el = line_el.find('cbc:LineExtensionAmount', NS)
    tax_total_el = line_el.find('cac:TaxTotal', NS)
    item_el = line_el.find('cac:Item', NS)
    desc_el = item_el.find(
        'cbc:Description', NS) if item_el is not None else None
    manufacturers_el = None
    if item_el is not None:
        manufacturers_el = item_el.find(
            'cac:ManufacturersItemIdentification/cbc:ID', NS)
        if manufacturers_el is None:
            man_agg = item_el.find('cac:ManufacturersItemIdentification', NS)
            if man_agg is not None:
                manufacturers_el = man_agg.find('cbc:ID', NS)
    sellers_el = item_el.find(
        'cac:SellersItemIdentification/cbc:ID', NS) if item_el is not None else None
    if item_el is not None and sellers_el is None:
        sellers_el = item_el.find('cac:SellersItemIdentification', NS)
        if sellers_el is not None:
            sellers_el = sellers_el.find('cbc:ID', NS)
    standard_el = None
    if item_el is not None:
        standard_el = item_el.find('cac:StandardItemIdentification', NS)
        if standard_el is not None:
            standard_el = standard_el.find('cbc:ID', NS)
    price_el = line_el.find('cac:Price', NS)
    price_amt_el = price_el.find(
        'cbc:PriceAmount', NS) if price_el is not None else None
    base_qty_el = price_el.find(
        'cbc:BaseQuantity', NS) if price_el is not None else None

    line_vals = {
        'line_number': int(_float(_text(line_id_el))),
        'note': '\n'.join(notes) if notes else None,
        'invoiced_quantity': credited_qty,
        'credited_quantity': credited_qty,
        'quantity_unit_code': qty_el.get('unitCode') if qty_el is not None else None,
        'line_extension_amount': _float(_text(line_ext_el)),
        'tax_total_ids': _parse_tax_total(tax_total_el),
        'description': _text(desc_el),
        'sellers_item_identification': _text(sellers_el),
        'standard_item_identification': _text(standard_el),
        'manufacturers_item_identification': _text(manufacturers_el),
        'price_amount': _float(_text(price_amt_el)),
        'base_quantity': _float(_text(base_qty_el)),
        'base_quantity_unit_code': base_qty_el.get('unitCode') if base_qty_el is not None else None,
    }
    return (0, 0, line_vals)


XML_STATES = [
    ('pending', 'Pending XML'),
    ('processing', 'Processing'),
    ('done', 'XML loaded'),
    ('error', 'Error'),
]
# Failed attempts (transient errors: timeout, HTTP error...) before giving up.
XML_MAX_ATTEMPTS = 3
# A document still in 'processing' after this many minutes belongs to a worker
# that died (server restart, time limit...) and is released back to 'pending'.
XML_STALE_MINUTES = 30
XML_DEFAULT_BATCH_SIZE = 10
XML_BATCH_SIZE_PARAM = 'l10n_co_bloodo.dian_document_xml_batch_size'
# Name the DIAN portal gives each document type (dian.document.type), used when the
# document is created from the XML (mail intake) instead of the portal.
INVOICE_TYPE_DIAN_NAMES = {
    '01': 'Factura electrónica',
    '02': 'Factura electrónica de exportación',
    '03': 'Factura electrónica de contingencia',
    '04': 'Factura electrónica de contingencia',
    '91': 'Nota de crédito electrónica',
    '92': 'Nota de débito electrónica',
}
# Fields filled by the DIAN portal synchronization. The XML only fills them when
# they are empty: the portal is the authoritative source.
PORTAL_FIELDS = (
    'type', 'result', 'radina_result', 'total_amount', 'tax_amount_5_percent',
    'tax_amount_19_percent', 'tax_amount_iva', 'tax_amount_ica', 'tax_amount_ipc',
)


class DianDocument(models.Model):
    _inherit = 'dian.document'

    sender_vat_xml = fields.Char(
        'Sender VAT (XML)',
        help='Sender NIT extracted from the XML '
             '(cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID, schemeName="31").',
    )
    sender_vat_match = fields.Boolean(
        'Sender VAT Match',
        compute='_compute_sender_vat_match',
        store=True,
        help='Indicates whether sender_vat (DIAN API) matches sender_vat_xml (XML).',
    )
    sender_id = fields.Many2one(
        'res.partner',
        string='Sender',
        compute='_compute_sender_id',
        store=True,
        ondelete='set null',
        help='Invoice issuer (vendor) found by NIT (sender_vat) in res.partner.vat.',
    )

    # Fields from XML
    xml_query_error_message = fields.Text('XML Query Error Message')
    # cbc:DocumentCurrencyCode
    # cbc:CreditNoteTypeCode (CreditNote) maps to the invoice_type field
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        ondelete='restrict',
    )
    # cbc:InvoiceTypeCode (Invoice) / cbc:CreditNoteTypeCode (CreditNote) -> invoice_type
    invoice_type = fields.Selection(
        selection=[
            ('', 'Invalid / Unspecified'),
            ('01', '01 - Electronic sales invoice'),
            ('02', '02 - Electronic export sales invoice'),
            ('03', '03 - Electronic transmission instrument - type 03'),
            ('04', '04 - Electronic sales invoice - type 04'),
            ('91', '91 - Credit note'),
            ('92', '92 - Debit note'),
            ('96', '96 - Events (ApplicationResponse)'),
            ('20', '20 - Electronic equivalent of POS cash register receipt'),
            ('25', '25 - Cinema admission ticket'),
            ('27', '27 - Public show admission ticket'),
            ('30', '30 - Localized and non-localized gaming - daily sales control report'),
            ('35', '35 - Land passenger transport ticket'),
            ('40', '40 - Toll collection document'),
            ('45', '45 - Statement issued by financial institutions and funds'),
            ('50', '50 - Air passenger transport ticket'),
            ('55', '55 - Stock exchange, agricultural and commodities operations document'),
            ('60', '60 - Public and residential utilities document'),
        ],
        string='Invoice Type Code',
        default='',
    )
    # cac:DiscrepancyResponse/cbc:ReferenceID (CreditNote: invoice being adjusted)
    discrepancy_reference_id = fields.Char(
        'Discrepancy Reference ID',
        size=32,
        help='Reference to the invoice being adjusted (cac:DiscrepancyResponse/cbc:ReferenceID).',
    )
    # cac:DiscrepancyResponse/cbc:ResponseCode (CreditNote: reason for the adjustment)
    discrepancy_response_code = fields.Char(
        'Discrepancy Response Code',
        size=8,
        help='Reason code for the credit/debit note (cac:DiscrepancyResponse/cbc:ResponseCode).',
    )
    # cac:PaymentMeans/cbc:PaymentMeansCode
    payment_means_code = fields.Selection(
        selection=[
            ('10', '10 - Cash'),
            ('49', '49 - Debit Card'),
            ('42', '42 - Bank consignment'),
            ('3', '3 - ACH Debit'),
            ('25', '25 - Certified cheque'),
            ('26', '26 - Local cheque'),
            ('24', '24 - Bill of exchange awaiting acceptance'),
            ('64', '64 - Promissory note signed by the bank'),
            ('65', '65 - Promissory note signed by a bank endorsed by another bank'),
            ('66', '66 - Signed promissory note'),
            ('67', '67 - Promissory note signed by a third party endorsed by a bank'),
            ('2', '2 - ACH Credit'),
            ('ZZZ', 'ZZZ - Other'),
            ('95', '95 - Open format draft'),
            ('13', '13 - Savings Credit'),
            ('14', '14 - Savings Debit'),
            ('39', '39 - Corporate Trade Exchange (CTX) Credit'),
            ('4', '4 - ACH demand debit reversal'),
            ('5', '5 - ACH demand credit reversal'),
            ('6', '6 - ACH demand credit'),
            ('7', '7 - ACH demand debit'),
            ('9', '9 - National or Regional clearing'),
            ('11', '11 - Savings credit reversal'),
            ('12', '12 - Savings debit reversal'),
            ('18', '18 - CCD debit disbursement'),
            ('19', '19 - Corporate Trade Payment (CTP) credit'),
            ('21', '21 - Bank draft'),
            ('22', '22 - Certified bank draft'),
            ('27', '27 - Corporate Trade Payment (CTP) debit'),
            ('28', '28 - Corporate Trade Exchange (CTX) credit'),
            ('29', '29 - Corporate Trade Exchange (CTX) debit'),
            ('30', '30 - Credit transfer'),
            ('31', '31 - Debit transfer'),
            ('32', '32 - CCD+ credit disbursement'),
            ('33', '33 - CCD+ debit disbursement'),
            ('34', '34 - Pre-authorized payment and deposit (PPD)'),
            ('35', '35 - CCD credit disbursement'),
            ('36', '36 - CCD debit disbursement'),
            ('48', '48 - Credit Card'),
            ('47', '47 - Bank debit transfer'),
            ('44', '44 - Bill of exchange'),
            ('20', '20 - Cheque'),
            ('23', '23 - Cashier\'s cheque'),
            ('71', '71 - Bonds'),
            ('72', '72 - Vouchers'),
            ('61', '61 - Promissory note signed by the creditor'),
            ('62', '62 - Promissory note signed by creditor, bank endorsed'),
            ('63', '63 - Promissory note signed by creditor, third party endorsed'),
            ('60', '60 - Promissory note'),
            ('96', '96 - Requested payment method not used'),
            ('91', '91 - Transferable bank note'),
            ('92', '92 - Transferable local cheque'),
            ('93', '93 - Referenced draft'),
            ('94', '94 - Urgent draft'),
            ('40', '40 - Corporate Trade Exchange (CTX) debit'),
            ('41', '41 - CCD+ credit disbursement'),
            ('43', '43 - CCD+ debit disbursement'),
            ('45', '45 - Bank credit transfer'),
            ('46', '46 - Interbank debit transfer'),
            ('50', '50 - Postal giro'),
            ('51', '51 - Standard bank telex'),
            ('52', '52 - Urgent commercial payment'),
            ('53', '53 - Urgent treasury payment'),
            ('15', '15 - Book entry credit'),
            ('16', '16 - Book entry debit'),
            ('17', '17 - CCD credit disbursement'),
            ('70', '70 - Note withdrawal by creditor'),
            ('74', '74 - Note withdrawal by creditor on a bank'),
            ('75', '75 - Note withdrawal by creditor, endorsed by another bank'),
            ('76', '76 - Note withdrawal by creditor, on a bank endorsed by third party'),
            ('77', '77 - Withdrawal of note by creditor on a third party'),
            ('78', '78 - Withdrawal of note by creditor on third party endorsed by bank'),
            ('1', '1 - Unspecified instrument'),
            ('37', '37 - Corporate Trade Payment (CTP) savings credit'),
            ('38', '38 - Corporate Trade Payment (CTP) savings debit'),
            ('97', '97 - Clearing between partners'),
        ],
        string='Payment Means Code',
        default='ZZZ',
        help='Payment means code (cac:PaymentMeans/cbc:PaymentMeansCode).',
    )
    # cac:LegalMonetaryTotal
    line_extension_amount = fields.Float(
        'Line Extension Amount',
        digits='Account',
        help='Sum of line amounts (cbc:LineExtensionAmount).',
    )
    tax_exclusive_amount = fields.Float(
        'Tax Exclusive Amount',
        digits='Account',
        help='Total without tax (cbc:TaxExclusiveAmount).',
    )
    tax_inclusive_amount = fields.Float(
        'Tax Inclusive Amount',
        digits='Account',
        help='Total with tax (cbc:TaxInclusiveAmount).',
    )
    payable_amount = fields.Float(
        'Payable Amount',
        digits='Account',
        help='Amount to pay (cbc:PayableAmount).',
    )
    # cac:TaxTotal (document-level)
    tax_total_ids = fields.One2many(
        'dian.document.tax.total',
        'document_id',
        string='Tax Totals',
    )
    # cac:InvoiceLine
    invoice_line_ids = fields.One2many(
        'dian.document.invoice.line',
        'document_id',
        string='Invoice Lines',
    )

    xml_state = fields.Selection(
        selection=XML_STATES,
        string='XML Status',
        default='pending',
        required=True,
        index=True,
        copy=False,
        readonly=True,
    )
    xml_attempts = fields.Integer(
        'XML Attempts',
        copy=False,
        readonly=True,
        help='Failed attempts to fetch the XML from DIAN.',
    )
    xml_processing_since = fields.Datetime(
        'XML Processing Since',
        copy=False,
        readonly=True,
    )
    xml_priority = fields.Boolean(
        'XML Requested',
        copy=False,
        readonly=True,
        help='Requested by a user from the wizard: processed before the rest.',
    )

    @api.model
    def _xml_to_document_vals(self, xml_content):
        """
        Parse UBL Invoice, CreditNote or DebitNote XML and return a dict of values for
        dian.document create(). Supports Invoice (cbc:InvoiceTypeCode, cac:InvoiceLine),
        CreditNote (cbc:CreditNoteTypeCode -> invoice_type, cac:DiscrepancyResponse,
        cac:CreditNoteLine) and DebitNote (no type code element: invoice_type = '92',
        cac:DiscrepancyResponse, cac:DebitNoteLine). Common: currency_id, PaymentMeans,
        LegalMonetaryTotal (RequestedMonetaryTotal on DebitNote), tax_total_ids.
        Returns empty dict and does not raise if XML is invalid or not one of those.
        """
        if not xml_content or not xml_content.strip():
            return {}
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return {}
        tag = (root.tag or '').split('}')[-1]
        if tag not in ('Invoice', 'CreditNote', 'DebitNote'):
            return {}

        vals = {}
        is_credit_note = tag == 'CreditNote'
        is_debit_note = tag == 'DebitNote'
        cac_ns = NS['cac']

        # cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID (schemeName="31")
        supplier_party = root.find('cac:AccountingSupplierParty/cac:Party', NS)
        if supplier_party is not None:
            company_id_el = supplier_party.find(
                'cac:PartyTaxScheme/cbc:CompanyID', NS)
            if company_id_el is None:
                company_id_el = supplier_party.find(
                    'cac:PartyLegalEntity/cbc:CompanyID', NS)
            if company_id_el is not None and _text(company_id_el):
                vals['sender_vat_xml'] = _text(company_id_el)

        # cbc:DocumentCurrencyCode -> currency_id
        doc_curr = root.find('cbc:DocumentCurrencyCode', NS)
        if doc_curr is not None and _text(doc_curr):
            code = _text(doc_curr)
            currency = self.env['res.currency'].search(
                [('name', '=', code)], limit=1
            )
            if currency:
                vals['currency_id'] = currency.id

        # cbc:InvoiceTypeCode (Invoice) / cbc:CreditNoteTypeCode (CreditNote) -> invoice_type.
        # UBL DebitNote has no type code element.
        if is_debit_note:
            vals['invoice_type'] = '92'
        type_code_el = root.find('cbc:InvoiceTypeCode', NS) if not is_credit_note else root.find(
            'cbc:CreditNoteTypeCode', NS)
        if not is_debit_note and type_code_el is not None and _text(type_code_el):
            code = _text(type_code_el)
            selection = self._fields['invoice_type'].selection
            if code in {v[0] for v in selection}:
                vals['invoice_type'] = code

        # CreditNote / DebitNote only: cac:DiscrepancyResponse
        if is_credit_note or is_debit_note:
            disc = root.find('cac:DiscrepancyResponse', NS)
            if disc is not None:
                ref_el = disc.find('cbc:ReferenceID', NS)
                if ref_el is not None and _text(ref_el):
                    vals['discrepancy_reference_id'] = _text(ref_el)
                resp_el = disc.find('cbc:ResponseCode', NS)
                if resp_el is not None and _text(resp_el):
                    vals['discrepancy_response_code'] = _text(resp_el)

        # cac:OrderReference/cbc:ID
        order_ref = root.find('cac:OrderReference', NS)
        if order_ref is not None:
            ref_id = order_ref.find('cbc:ID', NS)
            if ref_id is not None and _text(ref_id):
                vals['order_reference'] = _text(ref_id)

        # cac:PaymentMeans (Invoice, CreditNote and DebitNote)
        pay_means = root.find('cac:PaymentMeans', NS)
        if pay_means is not None:
            code_el = pay_means.find('cbc:PaymentMeansCode', NS)
            if code_el is not None and _text(code_el):
                code = _text(code_el)
                selection = self._fields['payment_means_code'].selection
                if code in {v[0] for v in selection}:
                    vals['payment_means_code'] = code

        # cac:LegalMonetaryTotal (cac:RequestedMonetaryTotal on DebitNote)
        mon_total = root.find(
            'cac:RequestedMonetaryTotal' if is_debit_note else 'cac:LegalMonetaryTotal', NS)
        if mon_total is not None:
            vals['line_extension_amount'] = _float(
                _text(mon_total.find('cbc:LineExtensionAmount', NS))
            )
            vals['tax_exclusive_amount'] = _float(
                _text(mon_total.find('cbc:TaxExclusiveAmount', NS))
            )
            vals['tax_inclusive_amount'] = _float(
                _text(mon_total.find('cbc:TaxInclusiveAmount', NS))
            )
            vals['payable_amount'] = _float(
                _text(mon_total.find('cbc:PayableAmount', NS))
            )

        # Document-level cac:TaxTotal (direct children of root only)
        doc_tax_totals = []
        for tax_total_el in root:
            if tax_total_el.tag == '{%s}TaxTotal' % cac_ns:
                doc_tax_totals.extend(_parse_tax_total(tax_total_el))
        if doc_tax_totals:
            vals['tax_total_ids'] = doc_tax_totals

        # cac:InvoiceLine (Invoice), cac:CreditNoteLine (CreditNote) or cac:DebitNoteLine (DebitNote)
        if is_credit_note:
            line_tag, parse_line = '{%s}CreditNoteLine' % cac_ns, _parse_credit_note_line
        elif is_debit_note:
            line_tag = '{%s}DebitNoteLine' % cac_ns

            def parse_line(line_el):
                return _parse_invoice_line(line_el, quantity_tag='cbc:DebitedQuantity')
        else:
            line_tag, parse_line = '{%s}InvoiceLine' % cac_ns, _parse_invoice_line
        invoice_lines = []
        for line_el in root:
            if line_el.tag == line_tag:
                invoice_lines.append(parse_line(line_el))
        if invoice_lines:
            vals['invoice_line_ids'] = invoice_lines

        return vals

    @api.depends('sender_vat', 'sender_vat_xml')
    def _compute_sender_vat_match(self):
        for rec in self:
            rec.sender_vat_match = bool(
                rec.sender_vat) and rec.sender_vat == rec.sender_vat_xml

    @api.depends('sender_vat', 'sender_vat_match')
    def _compute_sender_id(self):
        for rec in self:
            rec.sender_id = self.env['res.partner'].search(
                [('vat', '=', rec.sender_vat)], limit=1
            ) if rec.sender_vat_match else False

    # -------------------------------------------------------------------------
    # XML fetch (GetXmlByDocumentKey)
    # -------------------------------------------------------------------------

    @api.model
    def _xml_fetchable_domain(self):
        """Documents the cron may fetch: pending and of a company with direct e-invoicing."""
        return [
            ('xml_state', '=', 'pending'),
            ('company_id.type_einvoicing', '=', 'edi_dir'),
        ]

    @api.model
    def _xml_commit(self):
        """Commit the current transaction (never inside tests)."""
        if not modules.module.current_test:
            self.env.cr.commit()

    @api.model
    def _xml_rollback(self):
        """Roll back the current transaction (never inside tests)."""
        if not modules.module.current_test:
            self.env.cr.rollback()

    @api.model
    def _xml_release_stale(self):
        """Put back to 'pending' the documents left in 'processing' by a dead worker."""
        limit_date = fields.Datetime.now() - timedelta(minutes=XML_STALE_MINUTES)
        stale = self.sudo().search([
            ('xml_state', '=', 'processing'),
            '|',
            ('xml_processing_since', '=', False),
            ('xml_processing_since', '<', limit_date),
        ])
        if stale:
            _logger.warning(
                "DIAN XML: releasing %d document(s) stuck in 'processing': %s",
                len(stale), stale.ids)
            stale.write({'xml_state': 'pending', 'xml_processing_since': False})
            self._xml_commit()

    @api.model
    def _xml_claim(self, limit):
        """
        Lock up to `limit` fetchable documents (prioritary first), move them to
        'processing' and commit, so other transactions (the request wizard) see them
        as taken. Rows locked by another transaction are skipped, never waited for.
        """
        candidates = self.sudo().search(
            self._xml_fetchable_domain(),
            order='xml_priority desc, reception asc, id asc',
            limit=limit,
        )
        if not candidates:
            return candidates
        self.env.cr.execute("""
            SELECT id FROM dian_document
             WHERE id IN %s AND xml_state = 'pending'
               FOR UPDATE SKIP LOCKED
        """, [tuple(candidates.ids)])
        documents = candidates.browse([row[0] for row in self.env.cr.fetchall()])
        if documents:
            documents.write({
                'xml_state': 'processing',
                'xml_processing_since': fields.Datetime.now(),
            })
            self._xml_commit()
        return documents

    def _fetch_xml_content(self):
        """
        Download the XML of this document from DIAN (GetXmlByDocumentKey), signed
        with the certificate of the document's company.

        :return: dict with 'status' ('success'|'error') and either 'xml_content'
            (bytes) or 'message' and 'transient' (True when retrying may succeed).
        """
        self.ensure_one()
        company = self.company_id
        if not company.certificate_file:
            return {
                'status': 'error',
                'transient': False,
                'message': _("Company %s has no DIAN certificate configured.", company.name),
            }
        result = self.env['xml.by.document.key']._request_xml_by_document_key(
            self.cufe, company)
        if result['status'] != 'success':
            return result
        return {
            'status': 'success',
            'xml_content': b64decode(result['xml_b64']),
        }

    @api.model
    def _xml_vals_from_content(self, xml_content):
        """
        dian.document values from a received XML as DIAN or the issuer sends it
        (Invoice / CreditNote / DebitNote, possibly wrapped in an AttachedDocument).
        Besides _xml_to_document_vals, fills the portal fields (result, radina_result,
        type, total and tax summary) so a document created from the XML looks like a
        synchronized one. Returns an empty dict if the XML is not supported.
        """
        dian_result = _extract_dian_validation_result(xml_content)
        xml_content = _unwrap_attached_document(xml_content)
        vals = self._xml_to_document_vals(xml_content)
        if not vals:
            return {}
        if dian_result:
            vals['result'] = dian_result
        # DIAN only applies RADIAN events to invoices, not to credit/debit notes
        root_tag = _root_tag(xml_content)
        if root_tag == 'Invoice':
            vals['radina_result'] = 'Factura Electrónica'
        elif root_tag in ('CreditNote', 'DebitNote'):
            vals['radina_result'] = 'No Aplica'
        if vals.get('payable_amount'):
            vals['total_amount'] = vals['payable_amount']
        vals.update(_summarize_taxes(vals.get('tax_total_ids')))
        invoice_type = vals.get('invoice_type')
        if invoice_type:
            vals['type'] = INVOICE_TYPE_DIAN_NAMES.get(invoice_type) or dict(
                self._fields['invoice_type'].selection).get(invoice_type)
        return vals

    def _xml_write_values(self, xml_vals):
        """
        Values to write the parsed XML on this document: replaces previous lines/taxes
        and keeps the portal fields that are already set.
        """
        self.ensure_one()
        vals = {key: value for key, value in xml_vals.items()
                if key not in PORTAL_FIELDS or not self[key]}
        for field_name in ('invoice_line_ids', 'tax_total_ids'):
            if field_name in vals:
                vals[field_name] = [(5, 0, 0)] + vals[field_name]
        vals.update({
            'xml_state': 'done',
            'xml_query_error_message': False,
            'xml_processing_since': False,
            'xml_priority': False,
        })
        return vals

    def _xml_lock_state(self):
        """Lock this document's row (waiting for other transactions) and return its xml_state."""
        self.ensure_one()
        self.flush_recordset(['xml_state'])
        self.env.cr.execute(
            "SELECT xml_state FROM dian_document WHERE id = %s FOR UPDATE", [self.id])
        xml_state = self.env.cr.fetchone()[0]
        self.invalidate_recordset(['xml_state'])
        return xml_state

    def _xml_mark_failure(self, message, transient):
        """Register a failed attempt: back to 'pending' if it may be retried, else 'error'."""
        self.ensure_one()
        attempts = self.xml_attempts + 1
        retry = transient and attempts < XML_MAX_ATTEMPTS
        self.write({
            'xml_state': 'pending' if retry else 'error',
            'xml_attempts': attempts,
            'xml_query_error_message': message,
            'xml_processing_since': False,
            'xml_priority': False,
        })

    def _xml_process(self):
        """
        Fetch, parse and store the XML of each (claimed) document. Commits after each
        document so a failure only affects that document.
        """
        for document in self:
            try:
                result = document._fetch_xml_content()
                if document._xml_lock_state() != 'processing':
                    # Completed meanwhile by another source (the mail intake)
                    _logger.info("DIAN XML: document %s no longer processing, skipped", document.id)
                elif result['status'] == 'success':
                    xml_vals = document._xml_vals_from_content(result['xml_content'])
                    if xml_vals:
                        document.write(document._xml_write_values(xml_vals))
                    else:
                        document._xml_mark_failure(
                            _("The XML returned by DIAN is not a supported document "
                              "(Invoice, CreditNote or DebitNote) or could not be parsed."),
                            transient=False)
                else:
                    document._xml_mark_failure(result['message'], result.get('transient', False))
                self._xml_commit()
            except Exception as e:  # noqa: BLE001 - one document must not stop the batch
                self._xml_rollback()
                _logger.exception("DIAN XML: error processing document %s (cufe=%s)",
                                  document.id, document.cufe)
                if document._xml_lock_state() == 'processing':
                    document._xml_mark_failure(
                        _("Unexpected error fetching the XML: %s", e), transient=True)
                self._xml_commit()

    @api.model
    def _cron_fetch_xml(self, batch_size=None):
        """
        Cron: fetch the XML of the next batch of pending documents.

        Reports as 'remaining' only the documents requested from the wizard, so
        Odoo re-runs this cron right away until those are done, while the rest of
        the backlog advances one batch per scheduled run.
        """
        if not batch_size:
            batch_size = int(self.env['ir.config_parameter'].sudo().get_param(
                XML_BATCH_SIZE_PARAM, XML_DEFAULT_BATCH_SIZE))
        self._xml_release_stale()
        documents = self._xml_claim(batch_size)
        documents._xml_process()
        remaining = self.sudo().search_count(
            self._xml_fetchable_domain() + [('xml_priority', '=', True)])
        # Outside a cron run _commit_progress would only commit
        if self.env.context.get('ir_cron_progress_id'):
            self.env['ir.cron']._commit_progress(len(documents), remaining=remaining)
        _logger.info("DIAN XML: %d document(s) processed, %d requested remaining",
                     len(documents), remaining)

    @api.model
    def _xml_trigger_cron(self):
        # sudo: accounting users have no access to ir.cron
        cron = self.sudo().env.ref('l10n_co_bloodo.cron_dian_document_fetch_xml',
                                   raise_if_not_found=False)
        if cron and cron.active:
            cron._trigger()


class DianDocumentTaxTotal(models.Model):
    """
    Maps UBL cac:TaxTotal (document-level or within cac:InvoiceLine).
    Origin: cac:TaxTotal with TaxSubtotal (TaxableAmount, TaxAmount, Percent, TaxScheme).
    """
    _name = 'dian.document.tax.total'
    _description = 'DIAN Document Tax Total'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        readonly=True,
    )
    document_id = fields.Many2one(
        'dian.document',
        string='Document',
        ondelete='cascade',
        index=True,
    )
    invoice_line_id = fields.Many2one(
        'dian.document.invoice.line',
        string='Invoice Line',
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        compute='_compute_company_id',
        store=True,
        index=True,
    )
    # cbc:TaxAmount
    tax_amount = fields.Float(
        'Tax Amount',
        digits='Account',
    )
    # cac:TaxSubtotal / cbc:TaxableAmount
    taxable_amount = fields.Float(
        'Taxable Amount',
        digits='Account',
    )
    # cac:TaxCategory / cbc:Percent
    percent = fields.Float(
        'Percent',
        digits=(5, 2),
    )
    # cac:TaxScheme / cbc:ID
    tax_scheme_id = fields.Char(
        'Tax Scheme ID',
        size=10,
    )
    # cac:TaxScheme / cbc:Name
    tax_scheme_name = fields.Char(
        'Tax Scheme Name',
        size=64,
    )

    @api.depends('document_id.company_id', 'invoice_line_id.document_id.company_id')
    def _compute_company_id(self):
        # Document-level taxes hang from document_id, line-level ones from invoice_line_id
        for record in self:
            record.company_id = (record.document_id or record.invoice_line_id.document_id).company_id

    @api.depends('tax_scheme_name', 'tax_scheme_id', 'percent', 'tax_amount')
    def _compute_name(self):
        for record in self:
            parts = []
            if record.tax_scheme_name:
                parts.append(record.tax_scheme_name)
            elif record.tax_scheme_id:
                parts.append(record.tax_scheme_id)
            if record.percent is not None and record.percent != 0:
                parts.append('(%.2f%%)' % record.percent)
            if record.tax_amount is not None and record.tax_amount != 0:
                parts.append('- %s' % record.tax_amount)
            record.name = ' '.join(parts) if parts else 'Tax'


class DianDocumentInvoiceLine(models.Model):
    """
    Maps UBL cac:InvoiceLine.
    Origin: cac:InvoiceLine (ID, InvoicedQuantity, LineExtensionAmount,
    TaxTotal, Item Description/SellersItemIdentification/StandardItemIdentification,
    Price PriceAmount/BaseQuantity).
    """
    _name = 'dian.document.invoice.line'
    _description = 'DIAN Document Invoice Line'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        readonly=True,
    )
    document_id = fields.Many2one(
        'dian.document',
        string='Document',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='document_id.company_id',
        store=True,
        index=True,
    )
    # cbc:ID (line number)
    line_number = fields.Integer(
        'Line Number',
    )
    # cbc:Note (multiple); stored as text
    note = fields.Text(
        'Notes',
    )
    # cbc:InvoicedQuantity
    invoiced_quantity = fields.Float(
        'Invoiced Quantity',
        digits='Product Unit',
    )
    # cbc:InvoicedQuantity @unitCode
    quantity_unit_code = fields.Char(
        'Quantity Unit Code',
        size=10,
    )
    # cbc:CreditedQuantity (CreditNoteLine: credited quantity)
    credited_quantity = fields.Float(
        'Credited Quantity',
        digits='Product Unit',
        help='Quantity credited (cbc:CreditedQuantity in cac:CreditNoteLine).',
    )
    # cbc:LineExtensionAmount
    line_extension_amount = fields.Float(
        'Line Extension Amount',
        digits='Account',
    )
    # cac:TaxTotal (reuses dian.document.tax.total)
    tax_total_ids = fields.One2many(
        'dian.document.tax.total',
        'invoice_line_id',
        string='Tax Totals',
    )
    # cac:Item / cbc:Description
    description = fields.Text(
        'Description',
    )
    # cac:SellersItemIdentification / cbc:ID
    sellers_item_identification = fields.Char(
        'Sellers Item ID',
        size=64,
    )
    # cac:StandardItemIdentification / cbc:ID
    standard_item_identification = fields.Char(
        'Standard Item ID',
        size=64,
    )
    # cac:Item/cac:ManufacturersItemIdentification/cbc:ID (CreditNoteLine)
    manufacturers_item_identification = fields.Char(
        'Manufacturers Item ID',
        size=64,
        help='Manufacturer item ID (cac:ManufacturersItemIdentification/cbc:ID).',
    )
    # cac:Price / cbc:PriceAmount
    price_amount = fields.Float(
        'Price Amount',
        digits='Product Price',
    )
    # cac:Price / cbc:BaseQuantity
    base_quantity = fields.Float(
        'Base Quantity',
        digits='Product Unit',
    )
    # cac:Price / cbc:BaseQuantity @unitCode
    base_quantity_unit_code = fields.Char(
        'Base Quantity Unit Code',
        size=10,
    )

    @api.depends('line_number', 'description')
    def _compute_name(self):
        for record in self:
            num = record.line_number or 0
            desc = (record.description or '').strip()
            if desc:
                record.name = 'Line %s: %s' % (
                    num, desc[:80] + ('...' if len(desc) > 80 else ''))
            else:
                record.name = 'Line %s' % num
