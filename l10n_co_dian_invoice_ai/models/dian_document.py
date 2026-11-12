# -*- coding: utf-8 -*-
"""
Work queue of the invoice agent on dian.document: which documents it can process, the
run itself, and everything that does not go through the model (RADIAN events, credit
and debit note alerts, and the tacit acceptance deadline).
"""
import json
import logging
import re
from datetime import timedelta
import xml.etree.ElementTree as ET

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_co_bloodo.models.dian_document_xml import NS, _text

_logger = logging.getLogger(__name__)

AI_MAX_ATTEMPTS = 3
AI_STALE_MINUTES = 30
AI_CLASSIFY_LIMIT = 500
# Business days DIAN gives to claim before the invoice is tacitly accepted
TACIT_ACCEPTANCE_DAYS = 3
AI_CLOSED_EVENTS = ('031', '033', '034')
AI_PROMPT = (
    "Procesa el documento DIAN asignado: revísalo, crea la factura, crúzala contra el "
    "XML, revisa sus impuestos y finaliza. Tus herramientas ya actúan sobre ese documento."
)


def _digits(vat):
    return re.sub(r'\D', '', vat or '')


def _same_vat(vat_a, vat_b):
    """Compare two NIT with or without verification digit."""
    vat_a, vat_b = _digits(vat_a), _digits(vat_b)
    if not vat_a or not vat_b:
        return False
    return vat_a == vat_b or vat_a[:-1] == vat_b or vat_a == vat_b[:-1]


class DianDocument(models.Model):
    _name = 'dian.document'
    _inherit = ['dian.document', 'mail.thread', 'mail.activity.mixin']

    # ── Datos adicionales del XML ────────────────────────────────────────────
    xml_issue_date = fields.Date('Fecha de emisión (XML)', copy=False)
    xml_due_date = fields.Date('Fecha de vencimiento (XML)', copy=False)
    xml_tax_level_codes = fields.Char(
        'Responsabilidades del emisor (XML)', copy=False,
        help='cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode')
    xml_billing_reference = fields.Char(
        'Factura referenciada (XML)', copy=False,
        help='cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID')
    xml_billing_reference_cufe = fields.Char(
        'CUFE de la factura referenciada (XML)', copy=False,
        help='cac:BillingReference/cac:InvoiceDocumentReference/cbc:UUID')
    ai_xml_extras_loaded = fields.Boolean(copy=False)

    # ── Estado del agente ────────────────────────────────────────────────────
    ai_state = fields.Selection(
        [('inbox', 'En bandeja'),
         ('processing', 'Procesando'),
         ('exception', 'Excepción'),
         ('draft', 'Borrador para revisión'),
         ('posted', 'Causada'),
         ('review', 'Causada, para revisión'),
         ('note_alert', 'Nota crédito/débito por revisar'),
         ('note_reviewed', 'Nota crédito/débito revisada'),
         ('error', 'Error del agente')],
        'Estado del agente', copy=False, index=True)
    ai_exception_code = fields.Selection(
        [('xml_pending', 'XML pendiente'),
         ('xml_error', 'Error en el XML'),
         ('unsupported_type', 'Tipo de documento no soportado'),
         ('sender_mismatch', 'NIT del XML distinto al de la DIAN'),
         ('no_purchase', 'Sin orden de compra'),
         ('po_not_approved', 'Orden de compra sin aprobar'),
         ('partner_mismatch', 'Proveedor distinto al de la orden'),
         ('not_invoiceable', 'Orden sin cantidades por facturar')],
        'Motivo de excepción', copy=False)
    ai_detail = fields.Text('Detalle del agente', copy=False)
    ai_attempts = fields.Integer('Intentos del agente', copy=False)
    ai_processing_since = fields.Datetime(copy=False)
    ai_classified_on = fields.Datetime(copy=False)
    ai_compare_result = fields.Text('Último cruce contra el XML', copy=False)
    ai_033_requested = fields.Boolean(copy=False)
    ai_tacit_alert_sent = fields.Boolean(copy=False)
    ai_run_ids = fields.One2many('dian.ai.run', 'document_id', 'Ejecuciones')

    # ── XML ──────────────────────────────────────────────────────────────────

    @api.model
    def _xml_to_document_vals(self, xml_content):
        vals = super()._xml_to_document_vals(xml_content)
        if vals:
            vals.update(self._ai_xml_extras(xml_content))
        return vals

    @api.model
    def _ai_xml_extras(self, xml_content):
        """Fields of the XML that only the agent needs."""
        root = ET.fromstring(xml_content)
        due_date = _text(root.find('cbc:DueDate', NS)) or _text(
            root.find('cac:PaymentMeans/cbc:PaymentDueDate', NS))
        reference = root.find('cac:BillingReference/cac:InvoiceDocumentReference', NS)
        tax_level = _text(root.find(
            'cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode', NS))
        return {
            'xml_issue_date': _text(root.find('cbc:IssueDate', NS)) or False,
            'xml_due_date': due_date or False,
            'xml_tax_level_codes': tax_level or False,
            'xml_billing_reference': _text(reference.find('cbc:ID', NS)) if reference is not None else False,
            'xml_billing_reference_cufe': _text(reference.find('cbc:UUID', NS)) if reference is not None else False,
            'ai_xml_extras_loaded': True,
        }

    def _ai_load_xml_extras(self):
        """Documents loaded before installing this module have to fetch the XML again."""
        self.ensure_one()
        if self.ai_xml_extras_loaded:
            return
        result = self._fetch_xml_content()
        if result['status'] != 'success':
            raise UserError(result['message'])
        vals = self._xml_vals_from_content(result['xml_content'])
        if not vals:
            raise UserError(_('No se pudo leer el XML que devolvió la DIAN.'))
        self.write({key: value for key, value in vals.items()
                    if key.startswith('xml_') or key == 'ai_xml_extras_loaded'})

    # ── Bandeja y excepciones ────────────────────────────────────────────────

    def _ai_po_is_approved(self, order):
        """Confirmed order that, if the company uses the approval matrix, completed it."""
        if order.state != 'purchase':
            return False
        company = order.company_id
        if 'pr_approval_po' in company._fields and company.pr_approval_po:
            return order.approval_status == 'approved'
        return True

    def _ai_get_exception(self):
        """Return (code, detail) of the reason why the agent cannot process this document."""
        self.ensure_one()
        if self.xml_state in ('pending', 'processing'):
            return 'xml_pending', _('El XML aún no se ha descargado.')
        if self.xml_state == 'error':
            return 'xml_error', self.xml_query_error_message
        if self.invoice_type != '01':
            return 'unsupported_type', _(
                'El agente solo causa facturas tipo 01; este documento es %s.',
                self.invoice_type or self.type or _('desconocido'))
        if not self.sender_vat_match:
            return 'sender_mismatch', _(
                'El NIT de la DIAN (%(portal)s) no coincide con el del XML (%(xml)s).',
                portal=self.sender_vat, xml=self.sender_vat_xml)
        order = self.purchase_id
        if not order:
            return 'no_purchase', _('Sin orden de compra asociada: se causa manualmente.')
        if not self._ai_po_is_approved(order):
            return 'po_not_approved', _(
                'La orden %s no está aprobada.', order.name)
        if not _same_vat(order.partner_id.vat, self.sender_vat):
            return 'partner_mismatch', _(
                'El proveedor de la orden %(order)s (%(vat)s) no es el emisor del documento (%(sender)s).',
                order=order.name, vat=order.partner_id.vat, sender=self.sender_vat)
        return False, False

    def _ai_classify(self):
        """Put each document in the inbox or in the exceptions view, with its reason."""
        pending = self.filtered(lambda d: not d.move_id and d.ai_state in (False, 'inbox', 'exception'))
        pending.action_match_account_moves()
        pending.action_find_purchase_order()
        for document in pending:
            vals = {'ai_classified_on': fields.Datetime.now()}
            if document.move_id:
                vals.update({'ai_state': False, 'ai_exception_code': False, 'ai_detail': False})
            elif document.invoice_type in ('91', '92') and document.xml_state == 'done':
                vals.update({'ai_exception_code': False, 'ai_detail': False})
                document._ai_alert_note()
                vals['ai_state'] = 'note_alert'
            else:
                code, detail = document._ai_get_exception()
                vals.update({
                    'ai_state': 'exception' if code else 'inbox',
                    'ai_exception_code': code,
                    'ai_detail': detail,
                })
            document.write(vals)

    @api.model
    def _ai_release_stale(self):
        limit_date = fields.Datetime.now() - timedelta(minutes=AI_STALE_MINUTES)
        stale = self.sudo().search([
            ('ai_state', '=', 'processing'),
            '|', ('ai_processing_since', '=', False), ('ai_processing_since', '<', limit_date),
        ])
        if stale:
            _logger.warning("DIAN agent: releasing document(s) stuck in processing: %s", stale.ids)
            stale.write({'ai_state': 'inbox', 'ai_processing_since': False})
            self._xml_commit()

    @api.model
    def _ai_claim(self, company, limit):
        """Lock documents of the inbox and take them, so two runs never share a document."""
        candidates = self.sudo().search([
            ('company_id', '=', company.id),
            ('ai_state', '=', 'inbox'),
            ('move_id', '=', False),
        ], order='reception asc, id asc', limit=limit)
        if not candidates:
            return candidates
        self.env.cr.execute("""
            SELECT id FROM dian_document
             WHERE id IN %s AND ai_state = 'inbox'
               FOR UPDATE SKIP LOCKED
        """, [tuple(candidates.ids)])
        documents = candidates.browse([row[0] for row in self.env.cr.fetchall()])
        if documents:
            documents.write({'ai_state': 'processing', 'ai_processing_since': fields.Datetime.now()})
            self._xml_commit()
        return documents

    # ── Ejecución ────────────────────────────────────────────────────────────

    @api.model
    def _cron_ai_process(self):
        self._ai_release_stale()
        configs = self.env['dian.ai.config'].sudo().search([('enabled', '=', True)])
        for config in configs:
            company = config.company_id
            documents = self.sudo().search([
                ('company_id', '=', company.id),
                ('reception', '>=', config.start_date),
                ('ai_state', 'in', (False, 'inbox', 'exception')),
                ('move_id', '=', False),
            ], order='ai_classified_on asc nulls first, id asc', limit=AI_CLASSIFY_LIMIT)
            documents.with_company(company)._ai_classify()
            self._xml_commit()
            for document in self._ai_claim(company, config.batch_size):
                document._ai_process(config)
            self._ai_process_events(config)
            self._ai_alert_tacit_acceptance(config)
            self._xml_commit()

    def _ai_process(self, config):
        """Run the agent on one (claimed) document. The document ends up out of 'processing'."""
        self.ensure_one()
        collector = {}
        context = dict(self.env.context, dian_ai_document_id=self.id, ai_usage_collector=collector)
        user = config.user_id
        document = self.with_user(user).with_company(self.company_id).with_context(context)
        agent = config.agent_id.with_user(user).with_company(self.company_id).with_context(context)
        run = self.env['dian.ai.run'].sudo().create({
            'document_id': self.id,
            'agent_id': agent.id,
            'llm_model': agent.sudo().llm_model,
            'user_id': user.id,
        })
        document = document.with_context(dian_ai_run_id=run.id)
        agent = agent.with_context(dian_ai_run_id=run.id)
        self._xml_commit()
        try:
            document.check_access('write')
            document._ai_load_xml_extras()
            responses = agent.get_direct_response(AI_PROMPT, context_message=document._ai_system_context(config))
            if document.ai_state == 'processing':
                document._ai_stopped_without_finishing()
            if document.ai_state == 'exception':
                run.sudo().write({'outcome': 'exception', 'reasons': document.ai_detail})
            run.sudo().write({
                'response': '\n'.join(responses),
                'move_id': document.move_id.id,
                **document._ai_usage_vals(collector),
            })
            self._xml_commit()
        except Exception as e:  # noqa: BLE001 - one document must not stop the batch
            self._xml_rollback()
            _logger.exception("DIAN agent: error processing document %s", self.id)
            self._ai_mark_failure(run, e, collector)
            self._xml_commit()

    def _ai_usage_vals(self, collector):
        vals = {
            'input_tokens': collector.get('input_tokens', 0),
            'cached_tokens': collector.get('cached_tokens', 0),
            'output_tokens': collector.get('output_tokens', 0),
        }
        if collector.get('model'):
            vals['llm_model'] = collector['model']
        return vals

    def _ai_system_context(self, config):
        self.ensure_one()
        return _(
            "Compañía: %(company)s. Modo: %(mode)s. Umbral de confianza: %(threshold)s.",
            company=self.company_id.name,
            mode=dict(config._fields['mode'].selection)[config.mode],
            threshold=config.confidence_threshold,
        )

    def _ai_stopped_without_finishing(self):
        """The model ended its turn without calling the final tool."""
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('El agente terminó sin crear la factura ni finalizar el documento.'))
        self._ai_leave_draft([_('El agente terminó sin finalizar el documento.')])

    def _ai_mark_failure(self, run, error, collector=None):
        self.ensure_one()
        attempts = self.ai_attempts + 1
        message = str(error)
        final = attempts >= AI_MAX_ATTEMPTS
        self.sudo().write({
            'ai_state': 'error' if final else 'inbox',
            'ai_attempts': attempts,
            'ai_detail': message,
            'ai_processing_since': False,
        })
        run.sudo().write({
            'outcome': 'error',
            'reasons': message,
            **self._ai_usage_vals(collector or {}),
        })
        self.sudo().message_post(body=_(
            'Agente de causación: error en el intento %(attempt)s de %(max)s: %(error)s',
            attempt=attempts, max=AI_MAX_ATTEMPTS, error=message))
        if final:
            self.sudo()._ai_create_activity(_('El agente no pudo procesar el documento'), message)

    def action_ai_process(self):
        """Button: process now, with the permissions of the user of the configuration."""
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Solo un administrador de contabilidad puede ejecutar el agente.'))
        self.check_access('write')
        for document in self:
            config = document._ai_config()
            if not config:
                raise UserError(_(
                    'El agente no está activo para la compañía %s.', document.company_id.name))
            if document.ai_state == 'error':
                document.write({'ai_state': False, 'ai_attempts': 0})
            document.with_company(document.company_id)._ai_classify()
            if document.ai_state != 'inbox':
                continue
            document.sudo().write({'ai_state': 'processing', 'ai_processing_since': fields.Datetime.now()})
            document.sudo()._ai_process(config)
        return True

    def action_ai_refresh(self):
        self.check_access('write')
        for company, documents in self.grouped('company_id').items():
            documents.with_company(company)._ai_classify()
        return True

    def _ai_config(self):
        self.ensure_one()
        return self.env['dian.ai.config'].sudo().search([
            ('company_id', '=', self.company_id.id), ('enabled', '=', True),
        ], limit=1)

    def _ai_any_config(self):
        self.ensure_one()
        return self.env['dian.ai.config'].sudo().search([('company_id', '=', self.company_id.id)], limit=1)

    # ── Actividades y traza ──────────────────────────────────────────────────

    def _ai_review_user(self):
        config = self._ai_any_config()
        return config.review_user_id or config.user_id or self.env.user

    def _ai_create_activity(self, summary, note, record=None):
        """Create the review activity once per summary on the record (document by default)."""
        self.ensure_one()
        record = (record or self).sudo()
        if record.activity_ids.filtered(lambda a: a.summary == summary):
            return
        record.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=summary,
            note=note,
            user_id=self._ai_review_user().id,
        )

    def _ai_trace(self, tool, inputs, result):
        """Audit trail on the chatter of the document and of its invoice (CA-09)."""
        self.ensure_one()
        run = self.env['dian.ai.run'].sudo().browse(self.env.context.get('dian_ai_run_id'))
        body = Markup(
            '<p><b>%(title)s</b></p><ul>'
            '<li>%(l_agent)s: %(agent)s</li><li>%(l_model)s: %(model)s</li>'
            '<li>%(l_tool)s: %(tool)s</li><li>%(l_user)s: %(user)s</li>'
            '<li>%(l_in)s: %(inputs)s</li><li>%(l_out)s: %(result)s</li></ul>'
        ) % {
            'title': _('Agente de causación'),
            'l_agent': _('Agente'), 'agent': run.agent_id.sudo().name or '',
            'l_model': _('Modelo de IA'), 'model': run.llm_model or '',
            'l_tool': _('Herramienta'), 'tool': tool,
            'l_user': _('Usuario responsable'), 'user': self.env.user.name,
            'l_in': _('Datos de entrada'), 'inputs': json.dumps(inputs, ensure_ascii=False, default=str),
            'l_out': _('Resultado'), 'result': json.dumps(result, ensure_ascii=False, default=str)[:4000],
        }
        self.sudo().message_post(body=body)
        if self.move_id:
            self.move_id.sudo().message_post(body=body)

    # ── Notas crédito y débito ───────────────────────────────────────────────

    def _ai_referenced_invoice(self):
        """Return the (document, bill) a credit or debit note refers to."""
        self.ensure_one()
        reference = self.xml_billing_reference or self.discrepancy_reference_id
        cufe = self.xml_billing_reference_cufe
        domain = [('company_id', '=', self.company_id.id), ('invoice_type', '!=', self.invoice_type)]
        document = self.browse()
        if cufe:
            document = self.search(domain + [('cufe', '=', cufe)], limit=1)
        if not document and reference:
            document = self.search(domain + [('name', '=', reference), ('sender_vat', '=', self.sender_vat)], limit=1)
        move = document.move_id
        if not move and cufe:
            move = self.env['account.move'].search([
                ('company_id', '=', self.company_id.id), ('uuid_ei_ref', '=', cufe),
            ], limit=1)
        return document, move

    def _ai_alert_note(self):
        """The agent never posts credit or debit notes: it warns on the note and on the invoice."""
        self.ensure_one()
        document, move = self._ai_referenced_invoice()
        kind = _('nota crédito') if self.invoice_type == '91' else _('nota débito')
        reference = move.display_name or document.name or self.xml_billing_reference or self.discrepancy_reference_id
        summary = _('Revisar %s pendiente', kind)
        note = _(
            'La %(kind)s %(name)s hace referencia a la factura %(reference)s. Revísela y crúcela '
            'manualmente; el agente no causa notas.',
            kind=kind, name=self.name, reference=reference or _('sin identificar'))
        self.sudo().message_post(body=note)
        self._ai_create_activity(summary, note)
        for record in (document, move):
            if record:
                record.sudo().message_post(body=note)
                self._ai_create_activity(summary, note, record)

    def _ai_pending_notes(self):
        """Credit or debit notes not yet reviewed that refer to this document."""
        self.ensure_one()
        return self.search([
            ('company_id', '=', self.company_id.id),
            ('ai_state', '=', 'note_alert'),
            '|', ('xml_billing_reference_cufe', '=', self.cufe),
            '&', ('sender_vat', '=', self.sender_vat),
            '|', ('xml_billing_reference', '=', self.name), ('discrepancy_reference_id', '=', self.name),
        ])

    def action_ai_note_reviewed(self):
        self.check_access('write')
        notes = self.filtered(lambda d: d.ai_state == 'note_alert')
        notes.write({'ai_state': 'note_reviewed'})
        notes.activity_ids.action_feedback(feedback=_('Nota revisada'))
        return True

    # ── Eventos RADIAN (sin intervención del modelo) ─────────────────────────

    def _ai_goods_received(self):
        """Every invoiced quantity has been received (CA-08 / riesgo de recepción incompleta)."""
        self.ensure_one()
        lines = self.move_id.invoice_line_ids.filtered(
            lambda line: line.display_type == 'product' and line.quantity)
        if not lines:
            return False
        return all(
            line.purchase_line_id and line.purchase_line_id.qty_received >= line.quantity
            for line in lines
        )

    def _ai_addressed_to_company(self):
        self.ensure_one()
        return _same_vat(self.receiver_vat, self.company_id.vat)

    def _ai_next_event(self, config):
        """Next event this document needs, considering only what can be read locally."""
        self.ensure_one()
        display = self.ie_event_display or ''
        if display in AI_CLOSED_EVENTS or display.startswith('pending') \
                or not self._ai_addressed_to_company():
            return False
        if display not in ('030', '032'):
            return '030' if config.auto_event_030 else False
        move_posted = self.move_id.state == 'posted'
        if display == '030':
            if config.auto_event_032 and move_posted and self._ai_goods_received():
                return '032'
            return False
        if move_posted and self.ai_state == 'posted' and self._ai_goods_received():
            if config.auto_event_033:
                return '033'
            if not self.ai_033_requested:
                self.ai_033_requested = True
                self._ai_create_activity(
                    _('Aprobar aceptación expresa (033)'),
                    _('La factura %s quedó causada y cuadra con la orden y la recepción.',
                      self.move_id.display_name))
        return False

    def _ai_send_event(self, event):
        """Check the status at DIAN first: an event already registered is never repeated."""
        self.ensure_one()
        self.zustand_prufen(notif=False)
        errors = self._validate_event_sequence(event, self.ie_event_display)
        if errors:
            return False
        self._ereignis_senden(event)
        return True

    @api.model
    def _ai_process_events(self, config):
        company = config.company_id
        user = config.user_id
        documents = self.with_user(user).with_company(company).search([
            ('company_id', '=', company.id),
            ('reception', '>=', config.start_date),
            ('invoice_type', '=', '01'),
            ('xml_state', '=', 'done'),
            ('ie_event_display', 'not in', AI_CLOSED_EVENTS),
        ], order='reception asc, id asc')
        processed = 0
        for document in documents:
            if processed >= config.batch_size:
                break
            event = document._ai_next_event(config)
            if not event:
                continue
            processed += 1
            try:
                with self.env.cr.savepoint():
                    sent = document._ai_send_event(event)
                if sent:
                    document.sudo().message_post(body=_(
                        'Agente de causación: evento %(event)s enviado. Respuesta DIAN: %(response)s',
                        event=event, response=document.ev_fe_response or document.ie_event_display))
            except Exception as e:  # noqa: BLE001 - one document must not stop the batch
                _logger.warning("DIAN agent: event %s failed on document %s: %s", event, document.id, e)
                document.sudo().message_post(body=_(
                    'Agente de causación: no se pudo enviar el evento %(event)s: %(error)s',
                    event=event, error=str(e)))
            # DIAN already registered it: a later error must not undo the local record
            self._xml_commit()

    # ── Aceptación tácita ────────────────────────────────────────────────────

    def _ai_tacit_deadline(self):
        self.ensure_one()
        calendar = self.company_id.resource_calendar_id
        if calendar:
            return calendar.plan_days(TACIT_ACCEPTANCE_DAYS, self.reception)
        return self.reception + timedelta(days=TACIT_ACCEPTANCE_DAYS)

    @api.model
    def _ai_alert_tacit_acceptance(self, config):
        """Warn about unresolved documents close to being tacitly accepted."""
        company = config.company_id
        documents = self.sudo().with_company(company).search([
            ('company_id', '=', company.id),
            ('invoice_type', '=', '01'),
            ('ai_state', 'in', ('draft', 'exception', 'error', 'review')),
            ('ai_tacit_alert_sent', '=', False),
            ('ie_event_display', 'not in', AI_CLOSED_EVENTS),
            ('reception', '>=', config.start_date),
        ])
        now = fields.Datetime.now()
        for document in documents:
            deadline = document._ai_tacit_deadline()
            if deadline and deadline - timedelta(days=1) <= now:
                document._ai_create_activity(
                    _('Reclamo (031) próximo a vencer'),
                    _('El plazo para reclamar la factura %(name)s vence alrededor del %(deadline)s. '
                      'Si hay diferencias sin resolver, envíe el reclamo antes de esa fecha.',
                      name=document.name, deadline=fields.Datetime.to_string(deadline)))
                document.ai_tacit_alert_sent = True
