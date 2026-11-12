# -*- coding: utf-8 -*-

import base64
import io
import logging
import re
import zipfile

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class DianInvoiceIntake(models.Model):

    _name = 'dian.invoice.intake'
    _description = 'Bandeja de entrada - Facturas de proveedor por correo'
    _inherit = ['mail.thread']
    _order = 'id desc'
    _rec_name = 'name'
    _check_company_auto = True

    name = fields.Char('Referencia', default=lambda self: _('Nuevo'),
                       copy=False, readonly=True)
    email_from = fields.Char('Remitente', tracking=True)
    email_subject = fields.Char('Asunto')
    received_date = fields.Datetime('Fecha de recepción',
                                    default=fields.Datetime.now)
    state = fields.Selection(
        [
            ('new', 'Nuevo'),
            ('processed', 'Procesada'),
            ('partial', 'Procesada parcialmente'),
            ('skipped', 'Omitida (factura de venta propia)'),
            ('error', 'Error'),
        ],
        'Estado', default='new', tracking=True, copy=False)
    error_message = fields.Text('Detalle', copy=False)
    dian_document_ids = fields.Many2many(
        'dian.document', string='Registros en Facturas DIAN', copy=False,
        check_company=True)
    company_id = fields.Many2one(
        'res.company', 'Compañía', required=True,
        default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'dian.invoice.intake') or _('Nuevo')
        return super().create(vals_list)

    # ── Punto de entrada: correo entrante ───────────────────────────────

    def message_new(self, msg_dict, custom_values=None):
        custom_values = dict(custom_values or {})
        # Otherwise mail.thread uses the subject as name and create() skips the sequence
        custom_values.setdefault('name', _('Nuevo'))
        custom_values.setdefault('email_from', msg_dict.get('from'))
        custom_values.setdefault('email_subject', msg_dict.get('subject'))
        custom_values.setdefault(
            'received_date', msg_dict.get('date') or fields.Datetime.now())
        company_id = self._get_company_from_fetchmail_server()
        if company_id:
            custom_values.setdefault('company_id', company_id)
        return super().message_new(msg_dict, custom_values)

    def _get_company_from_fetchmail_server(self):
        # fetchmail.server sets default_fetchmail_server_id when processing the mail
        server_id = self.env.context.get('default_fetchmail_server_id')
        if not server_id:
            return False
        server = self.env['fetchmail.server'].sudo().browse(server_id)
        return server.exists() and server.company_id.id or False

    def _message_post_after_hook(self, message, msg_vals):
        result = super()._message_post_after_hook(message, msg_vals)

        if self.state == 'new':
            self._process_incoming_email()
        return result

    # ── Procesamiento (reutilizable también desde "Reintentar") ─────────

    def _process_incoming_email(self):
        self.ensure_one()
        try:
            xml_files = self._extract_xml_attachments()
            if not xml_files:
                self.write({
                    'state': 'error',
                    'error_message': _(
                        'El correo no trae ningún adjunto .xml o .zip '
                        'reconocible como factura electrónica.'),
                })
                return

            linked_docs = self.env['dian.document']
            filled_docs = self.env['dian.document']
            skipped = 0
            detail_lines = []

            for xml_b64_in, xml_fname_in in xml_files:
                try:
                    wizard = self.env['invoice.import.wizard'].create({
                        'doc_file_id': xml_b64_in,
                        'doc_fname': xml_fname_in,
                    })
                    xml_b64, xml_fname = wizard._get_xml_file()

                    werte = self.env['account.move'].new({}).decode_ei_xml_file(
                        xml_b64)

                    if self._is_own_issued_document(werte):
                        skipped += 1
                        detail_lines.append(_(
                            '%s: omitido (el emisor es esta misma '
                            'compañía).') % xml_fname_in)
                        continue

                    dian_doc, outcome = self._upsert_dian_document(werte, xml_b64)
                    if not dian_doc:
                        detail_lines.append(_(
                            '%s: error, el XML no trae CUFE (UUID) o no es un '
                            'documento soportado.') % xml_fname_in)
                        continue
                    linked_docs |= dian_doc
                    if outcome in ('created', 'filled'):
                        filled_docs |= dian_doc
                    detail_lines.append({
                        'created': _('%s: procesado, documento creado (%s).'),
                        'filled': _('%s: procesado, se completaron los datos del XML (%s).'),
                        'done': _('%s: el documento %s ya tenía los datos del XML, no se modificó.'),
                        'processing': _('%s: el documento %s se está obteniendo de la DIAN '
                                        'en este momento, no se modificó.'),
                    }[outcome] % (xml_fname_in, dian_doc.name))
                except Exception as error:
                    _logger.exception(
                        'Error procesando %s del correo %s',
                        xml_fname_in, self.name)
                    detail_lines.append(
                        _('%s: error, %s') % (xml_fname_in, error))

            self.dian_document_ids = [(6, 0, linked_docs.ids)]

            total = len(xml_files)
            ok = len(linked_docs)
            relevant = total - skipped
            if relevant == 0:
                new_state = 'skipped'
            elif ok == relevant:
                new_state = 'processed'
            elif ok > 0:
                new_state = 'partial'
            else:
                new_state = 'error'

            self.write({
                'state': new_state,
                'error_message': (
                    '\n'.join(detail_lines)
                    if (total > 1 or new_state != 'processed'
                        or filled_docs != linked_docs) else False),
            })

            if filled_docs and self.company_id.dian_intake_send_acknowledgment:
                try:
                    self._send_acknowledgment_email(filled_docs)
                except Exception:
                    _logger.exception(
                        'No se pudo enviar el correo de acuse para %s',
                        self.name)

        except Exception as error:
            _logger.exception(
                'Error procesando correo de factura recibida (%s)',
                self.name)
            self.write({
                'state': 'error',
                'error_message': str(error),
            })

    def _is_own_issued_document(self, werte):
        
        supplier = werte.get('AccountingSupplierParty') or {}
        supplier_vat = re.sub(r'\D', '', supplier.get('CompanyID') or '')
        if not supplier_vat:
            return False
        company = self.company_id or self.env.company
        own_vat = re.sub(
            r'\D', '', company.vat or (company.partner_id.vat or '') or '')
        return bool(own_vat) and supplier_vat == own_vat

    def _send_acknowledgment_email(self, dian_docs):
        
        self.ensure_one()
        if not self.email_from or not dian_docs:
            return
        company_currency = self.company_id.currency_id
        items = []
        for doc in dian_docs:
            currency = doc.currency_id or company_currency
            total = doc.total_amount or doc.payable_amount or 0.0
            items.append(
                '<li><b>%(name)s</b> — CUFE: %(cufe)s — Valor total: '
                '%(total)s %(currency)s</li>' % {
                    'name': doc.name or '',
                    'cufe': doc.cufe or '',
                    'total': self._format_money(total),
                    'currency': currency.name if currency else '',
                })
        plural = len(dian_docs) > 1
        subject = (
            _('Facturas recibidas (%s)') % len(dian_docs) if plural
            else _('Factura recibida - %s') % (dian_docs.name or ''))
        intro = (
            _('Hemos recibido y registrado sus facturas electrónicas:')
            if plural else
            _('Hemos recibido y registrado su factura electrónica:'))
        body = '<p>%s</p><ul>%s</ul><p>%s</p>' % (
            intro, ''.join(items),
            _('Este es un correo automático, no es necesario '
              'responderlo.'))
        self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body,
            'email_to': self.email_from,
            'auto_delete': True,
        }).send()

    def _format_money(self, amount):

        text = '{:,.2f}'.format(amount or 0.0)
        return text.replace(',', 'X').replace('.', ',').replace('X', '.')

    def _upsert_dian_document(self, werte, xml_b64):
        """
        Create the dian.document of the XML, or complete an existing one.

        An existing document (same CUFE and company) is never duplicated, and it is
        only completed when it still lacks its XML data: with its row locked, a
        document already 'done' is left as is, and one in 'processing' is left to the
        XML fetch cron that is handling it.

        :return: (dian.document, outcome) with outcome one of 'created', 'filled',
            'done', 'processing'; (False, False) if the XML has no CUFE or is not
            a supported document.
        """
        cufe = (werte.get('UUID') or '').strip()
        if not cufe:
            return False, False

        doc_model = self.env['dian.document']
        xml_vals = doc_model._xml_vals_from_content(base64.b64decode(xml_b64))
        if not xml_vals:
            return False, False
        company = self.company_id or self.env.company

        dian_doc = doc_model.search([
            ('cufe', '=', cufe),
            ('company_id', '=', company.id),
        ], limit=1)

        if dian_doc:
            xml_state = dian_doc._xml_lock_state()
            if xml_state in ('done', 'processing'):
                return dian_doc, xml_state
            dian_doc.write(dian_doc._xml_write_values(xml_vals))
            return dian_doc, 'filled'

        supplier = werte.get('AccountingSupplierParty') or {}
        create_vals = dict(xml_vals)
        create_vals.update({
            'company_id': company.id,
            'cufe': cufe,
            'name': werte.get('ID') or cufe,
            'reception': self.received_date or fields.Datetime.now(),
            'sender': supplier.get('Name') or '',
            'sender_vat': supplier.get('CompanyID') or '',
            'receiver': company.partner_id.name or company.name or '',
            'receiver_vat': company.partner_id.vat or company.vat or '',
            'xml_state': 'done',
        })
        return doc_model.create(create_vals), 'created'

    def _extract_xml_attachments(self):
        
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
        ])
        results = []
        for att in attachments:
            if not att.datas or not att.name:
                continue
            fname = att.name
            if fname.lower().endswith('.zip'):
                results.extend(self._extract_xml_from_zip(att.datas, fname))
            elif fname.lower().endswith('.xml'):
                results.append((att.datas, fname))
        return results

    def _extract_xml_from_zip(self, zip_b64, zip_fname):
       
        results = []
        try:
            zip_bytes = base64.b64decode(zip_b64)
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for entry_name in zf.namelist():
                    if entry_name.lower().endswith('.xml'):
                        content = zf.read(entry_name)
                        results.append(
                            (base64.b64encode(content), entry_name))
        except (zipfile.BadZipFile, KeyError, OSError) as error:
            _logger.warning(
                'No se pudo leer el zip %s: %s', zip_fname, error)
        return results

    # ── Acciones de UI ───────────────────────────────────────────────────

    def action_retry(self):
        # Retrying writes dian.document, which only accounting managers can access
        # (the mail gateway processes as superuser and is not affected)
        if not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_('Solo los administradores contables pueden reintentar '
                                'el procesamiento de la bandeja.'))
        for record in self:
            if record.state == 'skipped':
                continue
            record.error_message = False
            record._process_incoming_email()

    def action_view_dian_document(self):
        self.ensure_one()
        if len(self.dian_document_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Documento DIAN'),
                'res_model': 'dian.document',
                'view_mode': 'form',
                'res_id': self.dian_document_ids.id,
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documentos DIAN'),
            'res_model': 'dian.document',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.dian_document_ids.ids)],
        }
