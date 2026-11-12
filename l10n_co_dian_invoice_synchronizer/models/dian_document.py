# -*- coding: utf-8 -*-
from datetime import datetime, timezone
import re

from odoo import _, api, fields, models


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


def _parse_emission_date(emission_str):
    """
    Convert DIAN's EmissionDate (/Date(ms)/ at 00:00 UTC of the emission day) to a date.
    Taken in UTC on purpose: converting it to Colombia time would move it to the day before.
    """
    dt = _parse_reception(emission_str)
    return dt.date() if dt else False


class DianDocument(models.Model):
    _name = 'dian.document'
    _description = 'DIAN Electronic Invoice Document'
    _check_company_auto = True

    _cufe_company_uniq = models.Constraint(
        'UNIQUE(cufe, company_id)',
        'A DIAN document with this CUFE already exists in this company.',
    )

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
        check_company=True,
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
        readonly=True,
        check_company=True,
    )

    # DIAN basic fields
    cufe = fields.Char('CUFE', required=True, index=True)
    reception = fields.Datetime('Reception Date', required=True)
    emission_date = fields.Date('Emission Date', index=True)
    name = fields.Char('Series and Number', required=True)
    type = fields.Char('Document Type')
    type_code = fields.Char(
        'Document Type Code',
        help='DIAN document type code (DocumentTypeId), e.g. 01 invoice, 91 credit note, '
             '92 debit note.',
    )
    sender_vat = fields.Char('Sender VAT')
    sender = fields.Char('Sender Name')
    receiver_vat = fields.Char('Receiver VAT')
    receiver = fields.Char('Receiver Name')
    result = fields.Char('Result')
    status_code = fields.Integer(
        'Status Code',
        help='DIAN status code (Status), e.g. 1 approved, 10 approved with notification.',
    )
    radina_result = fields.Char('Radian Result')
    total_amount = fields.Float('Total Amount')
    tax_amount_5_percent = fields.Float('Tax 5%')
    tax_amount_19_percent = fields.Float('Tax 19%')
    tax_amount_iva = fields.Float('Tax IVA')
    tax_amount_ica = fields.Float('Tax ICA')
    tax_amount_ipc = fields.Float('Tax IPC')

    # cac:OrderReference/cbc:ID. Only the purchase order matching lives here; the
    # field itself is filled from the XML by l10n_co_bloodo (see dian_document_xml.py).
    order_reference = fields.Char(
        'Order Reference',
        help='Purchase order reference (cac:OrderReference/cbc:ID).',
    )

    @api.model
    def document_received_to_vals(self, document_received):
        """
        Transform one document dict from _get_documents_for_date_range into vals
        suitable for creating a dian.document record.

        :param document_received: dict returned by the API (with keys cufe, reception,
            name, type, sender_vat, sender, receiver_vat, receiver, result, radina_result,
            total_amount, emission_date, type_code, status_code, tax_amount_5_percent,
            tax_amount_19_percent, tax_amount_iva, tax_amount_ica, tax_amount_ipc)
        :return: dict of values for create(), with reception as datetime and emission_date
            as date
        """
        keys_to_keep = {
            'cufe', 'reception', 'name', 'type', 'sender_vat', 'sender',
            'receiver_vat', 'receiver', 'result', 'radina_result', 'total_amount',
            'emission_date', 'type_code', 'status_code',
            'tax_amount_5_percent', 'tax_amount_19_percent', 'tax_amount_iva',
            'tax_amount_ica', 'tax_amount_ipc',
        }
        vals = {k: document_received.get(
            k) for k in keys_to_keep if k in document_received}
        vals['reception'] = _parse_reception(vals.get('reception', ''))
        if 'emission_date' in vals:
            vals['emission_date'] = _parse_emission_date(vals['emission_date'])
        vals['document_type'] = 'received'
        return vals

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
