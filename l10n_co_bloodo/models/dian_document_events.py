# -*- coding: utf-8 -*-
import json
import logging
import time
from base64 import b64encode
from datetime import datetime, timedelta
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from . import ir_sentences as satz
from .dian_event_mixin import EVENT_CODES

_logger = logging.getLogger(__name__)


class DianDocument(models.Model):
    _name = 'dian.document'
    _inherit = ['dian.document', 'dian.event.mixin']

    # ── Campos adicionales para eventos ──────────────────────────────────────

    ie_claim_id = fields.Many2one(
        'dian.claim.concept',
        'Concepto de rechazo',
        copy=False)
    ie_event_active_date = fields.Datetime(
        'Fecha de registro del evento',
        copy=False)
    ie_event_history_ids = fields.One2many(
        'history.dian.event',
        'document_id',
        'Historial eventos',
        copy=False)
    ie_event_active_id = fields.Many2one(
        'history.dian.event',
        'Evento activo',
        compute='_compute_event_active_id',
        copy=False)

    @api.depends('ie_event_history_ids')
    def _compute_event_active_id(self):
        for record in self:
            event_id = record.ie_event_history_ids.filtered(
                lambda e: e.ev_active)
            record.ie_event_active_id = event_id[0] if event_id else False

    # ── Implementaciones de hooks de dian.event.mixin ────────────────────────

    def _get_cufe_for_status(self):
        return self.cufe

    def _get_event_receiver(self):
        '''El receptor del evento es el emisor de la factura (proveedor).'''
        partner = self.env['res.partner'].search(
            [('vat', '=', self.sender_vat)], limit=1)
        if not partner:
            raise ValidationError(
                _('No se encontró un tercero con el NIT %s', self.sender_vat))
        return partner

    def _get_event_claim(self):
        if not self.ie_claim_id:
            raise ValidationError(
                _('Se debe seleccionar un "Concepto de rechazo" para '
                  'enviar el evento de Rechazo.'))
        return self.ie_claim_id.dian_code, self.ie_claim_id.name

    def _get_ref_doc_type_code(self):
        self.ensure_one()

        # Si ya viene desde el XML, usarlo
        if self.invoice_type:
            return self.invoice_type

        # Fallback según el tipo de documento sincronizado
        mapping = {
            'Factura electrónica': '01',
            'Nota crédito electrónica': '91',
            'Nota débito electrónica': '92',
            'Documento soporte electrónico': '05',
            'Nota de ajuste documento soporte': '95',
        }

        return mapping.get(self.type, '')

    def _reshnugnsdaten_abrufen(self):
        # RIESGO: self.invoice_type solo se llena a partir del XML
        # (dian_document_xml.py: _xml_to_document_vals), que se obtiene de forma
        # asincrona con el cron "DIAN: Obtener XML de documentos recibidos". Mientras
        # el documento no tenga xml_state = 'done', _get_ref_doc_type_code depende
        # del mapeo por nombre de 'type'; si este no coincide, "algoritm" cae en
        # 'CUDE-SHA384' y DocTypeCode queda en '', incluso para facturas de venta
        # normales (tipo 01) que deberian usar 'CUFE-SHA384'. Esto no lanza una
        # excepcion, pero puede hacer que la DIAN rechace o procese mal los eventos
        # 030/032/033 para documentos recibidos sin XML.
        self.ensure_one()

        doc_type = self._get_ref_doc_type_code()

        algoritm = (
            'CUFE-SHA384'
            if doc_type in ('01', '02', '03', '04', '91', '92')
            else 'CUDE-SHA384'
        )

        return {
            'ID': self.name,
            'UUID_Algoritm': algoritm,
            'UUID': self.cufe,
            'DocTypeCode': doc_type,
        }

    def _get_edi_filenames(self, file_type):
        self.ensure_one()
        seq_map = {
            'ar': ('ar', 'dian.ar.sent', 'ar_sent'),
            'ad': ('ad', 'dian.ad.sent', 'ad_sent'),
            'zip': ('z',  'dian.zip.sent', 'zip_sent'),
        }
        if file_type not in seq_map:
            raise ValidationError(
                _('Tipo de archivo no reconocido para eventos: %s', file_type))
        prefix, seq_code, seq_field = seq_map[file_type]
        ext = '.zip' if file_type == 'zip' else '.xml'
        if not self.company_id.partner_id.vat:
            raise ValidationError(
                _('El NIT de %s no está establecido.', self.company_id.name))
        seq_id = self.sudo().company_id._get_or_create_sequence_dian_sent(
            seq_code, seq_field)
        seq_number = seq_id.next_by_id() if seq_id else False
        if not seq_number:
            raise ValidationError(
                _('No se pudo obtener número de secuencia para %s.', file_type))
        nnnnnnnnnn = self.company_id.partner_id.vat.zfill(10)
        ppp = '000'
        aa = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()).strftime('%y')
        dddddddd = '{:08x}'.format(int(seq_number)).upper()
        return f'{prefix}{nnnnnnnnnn}{ppp}{aa}{dddddddd}{ext}'

    def _xml_soap_werte_erhalten(self):
        return satz.get_xml_soap_values(
            self.company_id.certificate_file,
            self.company_id.certificate_password)

    def _bring_anfrage_unterzeichnet(self, exe_env, wsdl, art, dok):
        '''Para dian.document solo se usan consultas de estado de eventos.'''
        self.ensure_one()
        if art != 'abfrage_ev':
            raise ValidationError(
                _('Operación "%s" no soportada para documentos DIAN.', art))
        xml_soap_werte = self._xml_soap_werte_erhalten()
        uuid = self.env.context.get('status_uuid', False) or self.cufe
        xml_soap_werte['trackId'] = uuid
        xml_soap_werte['To'] = wsdl.replace('?wsdl', '')
        signiert_xml = satz.get_xml_soap_with_signature(
            satz.render_xml_edi(xml_soap_werte, 'GetStatusEvent'),
            xml_soap_werte['Id'],
            self.company_id.certificate_file,
            self.company_id.certificate_password)
        return etree.tostring(signiert_xml, encoding='unicode')

    def ereignisverlauf_erstellen(self, werte=False, ar_b64=False,
                                  ev_data=False, ev_b64=False, event_code=False):
        self.ensure_one()
        history_obj = self.env['history.dian.event']
        history_id = None
        resp_code = werte.get('response_code') if werte else None

        last_event_id = self.ie_event_history_ids.filtered(lambda e: e.ev_active)
        if last_event_id and last_event_id[0].dian_code == resp_code:
            ev_status = last_event_id[0].dian_code
            date_reg = last_event_id[0].dian_date_event
        elif werte and not werte.get('event_empty', False) \
                and (not last_event_id
                     or resp_code != last_event_id[0].dian_code
                     or resp_code == '04'):
            date_reg = False
            if werte.get('event_date'):
                date_reg = '%s %s' % (werte.get('event_date'),
                                      werte.get('event_time'))
                date_reg = (
                    datetime.strptime(date_reg, '%Y-%m-%d %H:%M:%S-05:00')
                    + timedelta(hours=5)
                ).strftime('%Y-%m-%d %H:%M:%S')

            h_val = {
                'exe_env': werte.get('exe_env'),
                'dian_number': werte.get('event_id'),
                'dian_uuid': werte.get('uuid'),
                'dian_date_event': date_reg,
                'dian_code': werte.get('response_code'),
                'dian_name': werte.get('response_desc'),
                'dian_ar_file': ar_b64,
                'dian_ar_fname': 'ApplicationResponseDIAN.xml',
                'dian_ar_json': json.dumps(werte, indent=4, ensure_ascii=False),
                'name': ev_data and ev_data.get('event_id') or werte.get('ref_id'),
                'ev_uuid': ev_data and ev_data.get('uuid') or werte.get('ref_uuid'),
                'document_id': self.id,
                'ev_active': True,
            }
            if ev_data:
                ev_id = self.env['dian.event'].search(
                    [('dian_code', '=', ev_data.get('response_code'))], limit=1)
                h_val.update({
                    'ev_code': ev_data.get('response_code'),
                    'ev_id': ev_id and ev_id.id or False,
                    'ev_ar_file': ev_b64,
                    'ev_ar_fname': (ev_data.get('ar_fname')
                                    or 'ApplicationResponseEvent.xml'),
                    'notes': '<br/>'.join(ev_data.get('note', [])),
                })
            self.ie_event_history_ids.write({'ev_active': False})
            history_id = history_obj.create(h_val)
            ev_status = history_id.dian_code
        else:
            ev_status = 'other'
            if self.ev_fe_state == '67':
                ev_status = '67'
            date_reg = False

        self.write({
            'ie_event_display': ev_status,
            'ie_event_active_date': date_reg,
        })
        return history_id

    # ── Acciones de eventos ───────────────────────────────────────────────────

    def dian_event_validate(self, event=''):
        '''
        Valida si el documento está en condiciones de enviar el evento.
        Retorna (True, '') o (False, mensaje_error).
        '''
        self.ensure_one()
        errors = []
        if not self.cufe:
            errors.append('- El documento no tiene CUFE.')
        if event:
            errors.extend(self._validate_event_sequence(event, self.ie_event_display))
        if errors:
            return False, '\n'.join(errors)
        return True, ''

    def dian_event_send_action(self, event='', to_process=0):
        '''Abre el wizard de eventos DIAN para los documentos seleccionados.'''
        event_name = dict(EVENT_CODES).get(event, 'Consultar Estado Eventos')
        docs_valid = []
        docs_invalid = []

        for record in self:
            is_valid, error = record.dian_event_validate(event)
            if not is_valid:
                docs_invalid.append((0, 0, {
                    'document_id': record.id,
                    'error': error,
                    'url_invoice': record.company_id.get_base_url()
                    + '/odoo/accounting/%s' % record.id,
                }))
            else:
                docs_valid.append(record.id)

        if not docs_valid and not docs_invalid:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Evento %s' % event_name,
                    'message': 'No hay documentos seleccionados para procesar el evento %s.' % event_name,
                    'type': 'warning',
                    'sticky': True,
                }
            }
        return {
            'type': 'ir.actions.act_window',
            'name': event_name,
            'res_model': 'dian.event.send.wizard',
            'view_mode': 'form',
            'context': {
                'default_event_name': event_name,
                'default_document_ids': [(6, 0, docs_valid)],
                'default_error_line_ids': docs_invalid,
                'default_action_todo': event,
                'default_to_process': to_process,
            },
            'target': 'new',
        }

    def _dian_event_process_pending(self, batch_commit=1):
        '''Procesa en lote los eventos pendientes de este recordset.'''
        start_time = time.perf_counter()
        qty_total = len(self)
        qty_ok = 0
        qty_error = 0
        for index, doc in enumerate(self, 1):
            try:
                if 'pending' not in (doc.ie_event_display or ''):
                    continue
                event = doc.ie_event_display.replace('pending', '')
                todo = '_ereignis_senden' if event else 'zustand_prufen'
                with self.env.cr.savepoint():
                    getattr(doc, todo)(event)
                    qty_ok += 1
            except Exception as err:
                _logger.warning([doc, err])
                with self.env.cr.savepoint():
                    doc.write({
                        'ie_event_display': 'other',
                        'ev_fe_state': 'other',
                        'ev_fe_response': 'Error enviando el evento %s: \n%s' % (
                            dict(EVENT_CODES).get(event, 'Consultar estado'), str(err)),
                    })
                    qty_error += 1
            if index % batch_commit == 0:
                self.env.cr.commit()
        self.env.cr.commit()
        time_total = time.perf_counter() - start_time
        time_avg = time_total / qty_total if qty_total else 0
        _logger.info('Eventos pendientes procesados: %s de %s. Errores: %s',
                     qty_ok, qty_total, qty_error)
        return {
            'total': qty_total,
            'ok': qty_ok,
            'error': qty_error,
            'time_total': round(time_total, 2),
            'time_avg': round(time_avg, 2),
        }
