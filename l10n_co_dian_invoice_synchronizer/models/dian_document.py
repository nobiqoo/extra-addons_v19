# -*- coding: utf-8 -*-
from datetime import datetime, timezone
import re
import xml.etree.ElementTree as ET

from odoo import _, api, fields, models

# UBL 2.1 namespaces (DIAN Colombia)
NS = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}


def _parse_reception(reception_str):
    """
    Convert Microsoft JSON date string to datetime (UTC).
    Format: /Date(1769817600000)/ or /Date(-1234567890)/ (milliseconds since epoch).
    """
    if not reception_str:
        return False
    match = re.search(r'/Date\((-?\d+)', str(reception_str))
    if not match:
        return False
    try:
        ms = int(match.group(1))
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.replace(tzinfo=None)  # Odoo Datetime fields expect naive UTC
    except (ValueError, OSError):
        return False


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


def _parse_invoice_line(line_el):
    """From a cac:InvoiceLine element, build vals for dian.document.invoice.line (0, 0, vals)."""
    line_id_el = line_el.find('cbc:ID', NS)
    notes = []
    for note_el in line_el.findall('cbc:Note', NS):
        t = _text(note_el)
        if t:
            notes.append(t)
    qty_el = line_el.find('cbc:InvoicedQuantity', NS)
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


class DianDocument(models.Model):
    _name = 'dian.document'
    _description = 'DIAN Electronic Invoice Document'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    # Odoo fields
    document_type = fields.Selection(
        selection=[('received', 'Received document')],
        string='Document Type',
        required=True,
        default='received',
    )

    # Sync that created this document (if any)
    sync_id = fields.Many2one(
        'dian.sync',
        string='Synchronization',
        ondelete='set null',
        index=True,
    )

    # Linked purchase order (matched via order_reference = purchase.order.name)
    purchase_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        ondelete='set null',
        check_company=True,
        help='Purchase order matched from order_reference.',
    )
    # Linked Odoo invoice (matched via cufe = uuid_ei_ref)
    move_id = fields.Many2one(
        'account.move',
        string='Invoice',
        ondelete='set null',
        check_company=True,
        readonly=True,
    )

    # DIAN basic fields
    cufe = fields.Char('CUFE', required=True, index=True)
    reception = fields.Datetime('Reception Date', required=True)
    name = fields.Char('Series and Number', required=True)
    type = fields.Char('Document Type')
    sender_vat = fields.Char('Sender VAT')
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
    sender = fields.Char('Sender Name')
    receiver_vat = fields.Char('Receiver VAT')
    receiver = fields.Char('Receiver Name')
    result = fields.Char('Result')
    radina_result = fields.Char('Radian Result')
    total_amount = fields.Float('Total Amount')
    tax_amount_5_percent = fields.Float('Tax 5%')
    tax_amount_19_percent = fields.Float('Tax 19%')
    tax_amount_iva = fields.Float('Tax IVA')
    tax_amount_ica = fields.Float('Tax ICA')
    tax_amount_ipc = fields.Float('Tax IPC')

    # Fields from XML
    has_xml_info = fields.Boolean('Has XML Information')
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
    # cac:OrderReference/cbc:ID
    order_reference = fields.Char(
        'Order Reference',
        help='Purchase order reference (cac:OrderReference/cbc:ID).',
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

    @api.model
    def _xml_to_document_vals(self, xml_content):
        """
        Parse UBL Invoice or CreditNote XML and return a dict of values for dian.document create().
        Supports Invoice (cbc:InvoiceTypeCode, cac:InvoiceLine) and CreditNote
        (cbc:CreditNoteTypeCode -> invoice_type, cac:DiscrepancyResponse, cac:PaymentMeans,
        cac:CreditNoteLine). Common: currency_id, LegalMonetaryTotal, tax_total_ids.
        Returns empty dict and does not raise if XML is invalid or not Invoice/CreditNote.
        """
        if not xml_content or not xml_content.strip():
            return {}
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return {}
        tag = (root.tag or '').split('}')[-1]
        if tag not in ('Invoice', 'CreditNote'):
            return {}

        vals = {}
        is_credit_note = tag == 'CreditNote'
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

        # cbc:InvoiceTypeCode (Invoice) / cbc:CreditNoteTypeCode (CreditNote) -> invoice_type
        type_code_el = root.find('cbc:InvoiceTypeCode', NS) if not is_credit_note else root.find(
            'cbc:CreditNoteTypeCode', NS)
        if type_code_el is not None and _text(type_code_el):
            code = _text(type_code_el)
            selection = self._fields['invoice_type'].selection
            if code in {v[0] for v in selection}:
                vals['invoice_type'] = code

        # CreditNote only: cac:DiscrepancyResponse
        if is_credit_note:
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

        # cac:PaymentMeans (Invoice and CreditNote)
        pay_means = root.find('cac:PaymentMeans', NS)
        if pay_means is not None:
            code_el = pay_means.find('cbc:PaymentMeansCode', NS)
            if code_el is not None and _text(code_el):
                code = _text(code_el)
                selection = self._fields['payment_means_code'].selection
                if code in {v[0] for v in selection}:
                    vals['payment_means_code'] = code

        # cac:LegalMonetaryTotal
        mon_total = root.find('cac:LegalMonetaryTotal', NS)
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

        # cac:InvoiceLine (Invoice) or cac:CreditNoteLine (CreditNote)
        line_tag = '{%s}CreditNoteLine' % cac_ns if is_credit_note else '{%s}InvoiceLine' % cac_ns
        parse_line = _parse_credit_note_line if is_credit_note else _parse_invoice_line
        invoice_lines = []
        for line_el in root:
            if line_el.tag == line_tag:
                invoice_lines.append(parse_line(line_el))
        if invoice_lines:
            vals['invoice_line_ids'] = invoice_lines

        return vals

    @api.model
    def document_received_to_vals(self, document_received):
        """
        Transform one document dict from _get_documents_for_date_range into vals
        suitable for creating a dian.document record.

        :param document_received: dict returned by the API (with keys cufe, reception,
            name, type, sender_vat, sender, receiver_vat, receiver, result, radina_result,
            total_amount, tax_amount_5_percent, tax_amount_19_percent, tax_amount_iva,
            tax_amount_ica, tax_amount_ipc, xml_query_result)
        :return: dict of values for create(), without xml_query_result and with
            reception as datetime
        """
        keys_to_keep = {
            'cufe', 'reception', 'name', 'type', 'sender_vat', 'sender',
            'receiver_vat', 'receiver', 'result', 'radina_result', 'total_amount',
            'tax_amount_5_percent', 'tax_amount_19_percent', 'tax_amount_iva',
            'tax_amount_ica', 'tax_amount_ipc',
        }
        vals = {k: document_received.get(
            k) for k in keys_to_keep if k in document_received}
        vals['reception'] = _parse_reception(vals.get('reception', ''))
        vals['document_type'] = 'received'

        xml_query_result = document_received.get('xml_query_result', {})
        if not xml_query_result:
            vals['has_xml_info'] = False
            vals['xml_query_error_message'] = _(
                "XML retrieval function disabled due to DIAN restrictions, contact support.")
            return vals

        status = xml_query_result.get('status')
        if status == 'error':
            vals['has_xml_info'] = False
            vals['xml_query_error_message'] = xml_query_result.get(
                'message', '')
            return vals

        vals['has_xml_info'] = True
        xml_content = xml_query_result.get('xml_content')
        if xml_content:
            xml_vals = self._xml_to_document_vals(xml_content)
            vals.update(xml_vals)
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

    def action_find_purchase_order(self):
        """Search purchase.order by order_reference (= purchase.order.name) and link it."""
        matched = 0
        for rec in self:
            if rec.purchase_id or not rec.order_reference:
                continue
            po = self.env['purchase.order'].search([
                ('name', '=', rec.order_reference),
                ('company_id', '=', rec.company_id.id),
            ], limit=1)
            if po:
                rec.purchase_id = po
                matched += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Purchase order search complete'),
                'message': _('%d purchase order(s) found and linked.') % matched,
                'type': 'success' if matched > 0 else 'warning',
                'sticky': False,
            },
        }

    def action_match_account_moves(self):
        """Match selected records with account.move via cufe = uuid_ei_ref. Returns a notification."""
        already_linked = self.filtered(lambda d: d.move_id)
        to_process = self - already_linked
        cufes = to_process.mapped('cufe')
        moves = self.env['account.move'].search([
            ('uuid_ei_ref', 'in', cufes),
            ('company_id', 'in', to_process.mapped('company_id').ids),
        ])
        cufe_to_move = {
            (m.company_id.id, m.uuid_ei_ref): m for m in moves if m.uuid_ei_ref
        }
        matched = 0
        for doc in to_process:
            move = cufe_to_move.get((doc.company_id.id, doc.cufe))
            if move:
                doc.move_id = move
                matched += 1
        not_matched = len(to_process) - matched
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Matching complete'),
                'message': _(
                    '%d documents linked, %d not matched, %d already had an invoice.'
                ) % (matched, not_matched, len(already_linked)),
                'type': 'success' if matched > 0 else 'warning',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


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
        digits='Product Unit of Measure',
    )
    # cbc:InvoicedQuantity @unitCode
    quantity_unit_code = fields.Char(
        'Quantity Unit Code',
        size=10,
    )
    # cbc:CreditedQuantity (CreditNoteLine: credited quantity)
    credited_quantity = fields.Float(
        'Credited Quantity',
        digits='Product Unit of Measure',
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
        digits='Product Unit of Measure',
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
