# -*- coding: utf-8 -*-
import logging
from base64 import b64encode, b64decode
from datetime import datetime
from lxml import etree
from requests import post, exceptions
from odoo import _, fields, models
from odoo.exceptions import ValidationError
from . import ir_sentences as satz

_logger = logging.getLogger(__name__)

DIAN = {
    'wsdl-hab':
    'https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc?wsdl',
    'wsdl':
    'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl',
    'catalogo-hab':
    'https://catalogo-vpfe-hab.dian.gov.co'
    '/document/searchqr?documentkey={}',
    'catalogo':
    'https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey={}'
}

EVENT_CODES = [
    ('02', '[02] Documento validado por la DIAN'),
    ('04', '[03] Documento rechazado por la DIAN'),
    ('030', '[030] Acuse de recibo'),
    ('031', '[031] Reclamo'),
    ('032', '[032] Recibo del bien'),
    ('033', '[033] Aceptación expresa'),
    ('034', '[034] Aceptación Tácita'),
    ('67', '[67] Sin eventos asociados'),
    ('other', 'Error desconocido'),
    ('pending', 'Pendiente consulta de estado'),
    ('pending030', 'Pendiente de Acuse de recibo'),
    ('pending032', 'Pendiente de Recibo del bien'),
    ('pending033', 'Pendiente de Aceptación expresa'),
    ('035', '[035] Aval'),
    ('036', '[036] Inscripción en el RADIAN de la factura electrónica de venta como título valor que circula en el territorio nacional'),
    ('037', '[037] Endoso en propiedad'),
    ('038', '[038] Endoso en garantía'),
    ('039', '[039] Endoso en procuración'),
    ('040', '[040] Cancelación de endoso'),
    ('041', '[041] Limitación para circulación de la FE como título valor'),
    ('042', '[042] Terminación de la limitación para circulación de la FE como título valor'),
    ('043', '[043] Mandato'),
    ('044', '[044] Terminación del mandato'),
    ('045', '[045] Pago de la FE como título valor'),
    ('046', '[046] Informe para el pago'),
    ('047', '[047] Endoso con efectos de cesión ordinaria'),
    ('048', '[048] Protesto'),
    ('049', '[049] Transferencia de los derechos económicos'),
    ('050', '[050] Notificación al deudor sobre la transferencia de los derechos económicos'),
    ('051', '[051] Pago de la transferencia de los derechos económicos'),
]

ANFRAGEART = {
    'SendBillSync': 'Envío de doc. electrónico',
    'SendTestSetAsync': 'Envío de doc. electrónico (Pruebas)',
    'GetStatus': 'Consulta de estado DIAN',
    'GetStatusZip': 'Consulta de estado DIAN (Pruebas)',
    'GetStatusEvent': 'Consulta de estado del evento DIAN',
}


class DianEventMixin(models.AbstractModel):
    '''
    Mixin con toda la lógica de ejecución de eventos DIAN.
    Los modelos concretos heredan este mixin con _inherit e implementan los
    hooks con sus propios campos y fuentes de datos. En 19 solo lo usa
    dian.document; account.move conserva su propia lógica de eventos.
    '''
    _name = 'dian.event.mixin'
    _description = "Dian Event Mixin"

    # ── Campos compartidos ────────────────────────────────────────────────────

    ie_event_display = fields.Selection(
        EVENT_CODES,
        'Estado evento',
        copy=False,
        help='Evento activo del documento electrónico. '
             'Consulte el estado para mantenerlo actualizado.')
    ev_fe_state = fields.Char(
        'Estado de envío del evento',
        default=False,
        copy=False,
        help='Código de estado del evento entregado a la DIAN')
    ev_fe_response = fields.Text(
        'Respuesta de entrega evento',
        copy=False,
        help='Mensaje de respuesta de la entrega del evento. '
             'Aquí puede ver la lista de validaciones para corregir '
             'si el evento ha sido rechazado.')
    ev_check_date = fields.Date(
        'Fecha consulta evento DIAN',
        help='Fecha de la última consulta del estado del evento DIAN')
    ev_fe_user_id = fields.Many2one(
        'res.users',
        'Usuario evento',
        help='Usuario que realizó el último evento en el documento electrónico',
        copy=False)

    # ── Lógica de ejecución de eventos ───────────────────────────────────────

    def _ereignis_senden(self, ev_code):
        '''
        Orquesta la generación, envío y registro de un evento DIAN.
        '''
        exe_env = self.company_id.target_environment_id
        ereigniswerte = self._daten_fur_ereignis_abrufen(ev_code)
        xml_str = self._ereignis_xml_fullen(ereigniswerte)
        antwort = self.ereignis_senden_anfrage(xml_str)
        if antwort.get('zustand_kod') == '00':
            uuid = self._get_cufe_for_status()
            if not uuid:
                raise ValidationError(
                    _('No hay un CUFE de referencia para consultar estado.'))
            self = self.with_context(status_uuid=uuid)
            antwort = self.ereignis_status_erhalten(exe_env)
        out = self.die_ereignisantwort_verarbeiten(
            antwort, xml_str, exe_env, ev_code)
        return out

    def _daten_fur_ereignis_abrufen(self, event):
        '''
        Construye el diccionario de datos necesario para generar el XML del evento.
        Llama a los hooks para obtener los datos dependientes del modelo concreto.
        '''
        self.ensure_one()
        if event not in ('030', '031', '032', '033', '034'):
            raise ValidationError(
                _('El código de evento que está intentando enviar '
                  'es incorrecto.\nLos códigos permitidos son: \n\n'
                  '030:    Acuse de recibo de Factura Electrónica de Venta\n'
                  '031:    Reclamo de la Factura Electrónica de Venta\n'
                  '032:    Recibo del bien o prestación del servicio\n'
                  '033:    Aceptación expresa\n'
                  '034:    Aceptación Tácita'))
        event_id = self.env['dian.event'].search([('dian_code', '=', event)])
        exe_env = self.company_id.target_environment_id
        biller = self.company_id.partner_id
        receiver = self._get_event_receiver()
        person = self._get_event_user_partner()
        SoftId = self.company_id.software_id
        SoftPin = self.company_id.software_pin

        date_now = fields.Datetime.context_timestamp(self, datetime.now())
        NumDoc = self.env['ir.sequence'].next_by_code('ei.event.sequence')
        FecDoc = date_now.strftime('%Y-%m-%d')
        HorDoc = date_now.strftime('%H:%M:%S-05:00')
        ref_ei = self._reshnugnsdaten_abrufen()
        sscode = satz.ssc_erhalten(SoftId, SoftPin, NumDoc)
        receiver_vat = receiver.vat
        if event == '034':
            receiver_vat = '800197268'
        cude = satz.get_cufe_cude([NumDoc, FecDoc, HorDoc, biller.vat,
                                   receiver_vat, event, ref_ei.get('ID'),
                                   ref_ei.get('DocTypeCode'), SoftPin])
        if exe_env == '1':
            QRCodeURL = DIAN['catalogo']
        else:
            QRCodeURL = DIAN['catalogo-hab']
        QRCodeURL = QRCodeURL.format(ref_ei['UUID'])
        notes = []
        sender_party = satz.escape_xml(biller._ar_personendetails_erhalten())
        receiver_party = satz.escape_xml(receiver._ar_personendetails_erhalten())

        werte = {
            'ProviderIDschemeID': biller.l10n_co_verification_code,
            'ProviderIDschemeName':
            biller.l10n_latam_identification_type_id.dian_code,
            'ProviderID': biller.vat,
            'SoftwareID': SoftId,
            'SoftwareSecurityCode': sscode['SSC'],
            'QRCode': QRCodeURL,
            'ProfileExecutionID': exe_env,
            'ID': NumDoc,
            'UUID': cude['uuid'],
            'IssueDate': FecDoc,
            'IssueTime': HorDoc,
            'Notes': satz.escape_xml(notes),
            'SenderParty': sender_party,
            'ReceiverParty': receiver_party,
            'EventCode': event_id.dian_code,
            'EventName': event_id.name,
            'RefID': ref_ei.get('ID'),
            'RefUUID_Algoritm': ref_ei.get('UUID_Algoritm'),
            'RefUUID': ref_ei.get('UUID'),
            'RefDocTypeCode': ref_ei.get('DocTypeCode'),
        }
        if event == '031':
            claim_code, claim_name = self._get_event_claim()
            werte = dict(werte, **{
                'EventListID': claim_code,
                'EventListName': claim_name,
            })
        elif event == '034':
            txt_ev = self.env.context.get('note_ev_034')
            if txt_ev:
                notes.append(txt_ev)
                werte = dict(werte, **{
                    'Notes': notes,
                    'ReceiverParty': {
                        'RegistrationName': 'Unidad Especial Dirección de Impuestos y Aduanas Nacionales',
                        'schemeName': '31',
                        'schemeID': '4',
                        'AdditionalAccountID': '1',
                        'CompanyID': '800197268',
                        'TaxSchemeID': '01',
                        'TaxSchemeName': 'IVA'
                    }
                })
        elif event in ('030', '032'):
            werte = dict(werte, **{
                'Person': satz.escape_xml(person._ar_person_erhalten())
            })
        return werte

    def _ereignis_xml_fullen(self, werte):
        '''
        Genera y firma el XML del evento usando las credenciales de la compañía.
        '''
        self.ensure_one()
        unsigned_xml = satz.render_xml_edi(werte, 'AppDocEvent')
        xml_mit_signatur = satz.xml_mit_signatur_erhalten(
            unsigned_xml,
            self.company_id.signature_policy_url,
            self.company_id.signature_policy_description,
            self.company_id.signature_policy_file,
            self.company_id.certificate_file,
            self.company_id.certificate_password
        )
        return xml_mit_signatur

    def ereignis_senden_anfrage(self, xml):
        '''
        Empaqueta y envía el XML del evento al servicio SOAP de la DIAN.
        '''
        self.ensure_one()
        wsdl = DIAN['wsdl-hab']
        anfrageart = 'SendEventUpdateStatus'
        exe_env = self.company_id.target_environment_id
        if exe_env == '1':
            wsdl = DIAN['wsdl']
        vals_to_zip = [(self._get_edi_filenames('ar'), b64encode(xml))]
        xml_zip = satz.get_zipped_file(vals_to_zip)
        SendEvent_werte = self._xml_soap_werte_erhalten()
        SendEvent_werte['contentFile'] = b64encode(
            xml_zip).decode('utf-8', 'ignore')
        SendEvent_werte['To'] = wsdl.replace('?wsdl', '')
        signiert_xml = satz.get_xml_soap_with_signature(
            satz.render_xml_edi(SendEvent_werte, 'SendEventUpdateStatus'),
            SendEvent_werte['Id'],
            self.company_id.certificate_file,
            self.company_id.certificate_password
        )
        anfrage = etree.tostring(signiert_xml, encoding='unicode')
        _logger.info('********************** SendEventUpdateStatus')
        try:
            antwort = post(
                wsdl,
                headers={'content-type': 'application/soap+xml;charset=utf-8'},
                data=anfrage
            )
            if antwort.status_code == 200:
                daten_antwort = satz.datenantwort_erhalten(antwort)
                self.versandlog_erstellen(anfrageart, daten_antwort, anfrage, exe_env)
                daten_antwort = dict(daten_antwort, **{
                    'ar_fname': vals_to_zip[0][0]
                })
                return daten_antwort
            elif antwort.status_code in (500, 503, 507):
                self.versandlog_erstellen(
                    anfrageart,
                    {
                        'status_code': antwort.status_code,
                        'reason': antwort.reason,
                        'response_text': antwort.text.replace('><', '>\n<'),
                    },
                    anfrage,
                    exe_env
                )
            else:
                raise ValidationError(
                    _('Error desconocido en metodo %s. \n\n Contacte con su '
                      'administrador.\n\nCódigo estado: %s.\n Razón: %s',
                      anfrageart, antwort.status_code, antwort.reason))
        except exceptions.RequestException as e:
            raise ValidationError(
                _('Error desconocido en metodo %s. \nContacte con su '
                  'administrador.\n\n%s', anfrageart, e))
        return True

    def ereignis_status_erhalten(self, exe_env):
        '''
        Consulta el estado del evento ante la DIAN vía SOAP.
        '''
        self.ensure_one()
        wsdl = DIAN['wsdl-hab']
        if exe_env == '1':
            wsdl = DIAN['wsdl']
        art = 'abfrage_ev'
        anfrage = self._bring_anfrage_unterzeichnet(exe_env, wsdl, art, False)
        antwort = post(
            wsdl,
            headers={'content-type': 'application/soap+xml;charset=utf-8'},
            data=anfrage
        )
        if antwort.status_code == 200:
            daten_antwort = satz.datenantwort_erhalten(antwort)
            if self.env.context.get('ev_status_log'):
                self.versandlog_erstellen(
                    'GetStatusEvent', daten_antwort, anfrage, exe_env)
            return daten_antwort
        else:
            raise ValidationError(
                _('Error en metodo GetStatusEvent.\n'
                  'Estado: %s \nRazón: %s',
                  antwort.status_code, antwort.reason))

    def zustand_prufen(self, notif=True):
        '''
        Consulta el estado del documento en la DIAN y actualiza el historial.
        '''
        exe_env = self.company_id.target_environment_id
        uuid = self._get_cufe_for_status()
        if not uuid:
            raise ValidationError(
                _('No hay un CUFE de referencia para '
                  'consultar el estado.'))
        self = self.with_context(status_uuid=uuid)
        daten_antwort = self.ereignis_status_erhalten(exe_env)
        if isinstance(daten_antwort, dict):
            self._write_status_check_event(daten_antwort)
            ar_b64 = daten_antwort.get('xml_base64')
            ar_xml = ar_b64 and b64decode(ar_b64).decode() or None
            ar_data = ar_xml and satz.daten_aus_ar_extrahieren(ar_xml) or {}
            history_ev_id = self.ereignisverlauf_erstellen(ar_data, ar_b64)
            self.ev_check_date = fields.Date.today()
            if not history_ev_id and notif:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'SIN EVENTOS.',
                        'message': _('No hay eventos registrados en la DIAN '
                                     'para el documento %s', self.name),
                        'type': 'warning',
                        'sticky': True,
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }

    def _write_status_check_event(self, antwort):
        self.ensure_one()
        zustand_kod = antwort.get('zustand_kod', 'other')
        bild = ' \n'.join(list(filter(
            lambda x: x,
            [
                antwort.get('zustand_beschreiben', ''),
                antwort.get('zustand_nachricht', ''),
                ''.join([
                    '\n- %s.' % f for f in antwort.get('fehlerliste', [])
                ])
            ]
        )))
        if not bild:
            bild = antwort.get('response_text', '').replace('><', '>\n<')
        self.write({'ev_fe_state': zustand_kod, 'ev_fe_response': bild})

    def die_ereignisantwort_verarbeiten(self, antwort, ev_xml, exe_env, ev_code):
        '''
        Procesa la respuesta de la DIAN: escribe el estado, crea el historial
        y delega el postprocesado (documento adjunto, correo) al hook _post_event_response.
        '''
        self.ensure_one()
        zustand_kod = antwort.get('zustand_kod', 'other')
        bild = ' \n'.join(list(filter(
            lambda x: x,
            [
                antwort.get('zustand_beschreiben', ''),
                antwort.get('zustand_nachricht', ''),
                ''.join([
                    '\n- %s.' % f for f in antwort.get('fehlerliste', [])
                ])
            ]
        )))
        if not bild:
            bild = antwort.get('response_text', '').replace('><', '>\n<')
        self.write({'ev_fe_state': zustand_kod, 'ev_fe_response': bild})
        ar_b64 = antwort.get('xml_base64')
        ar_xml = b64decode(ar_b64).decode()
        ar_data = satz.daten_aus_ar_extrahieren(ar_xml)
        ev_b64 = b64encode(ev_xml)
        ev_data = satz.daten_aus_ar_extrahieren(ev_xml)
        ev_data['ar_fname'] = antwort.get('ar_fname')
        event_log_id = self.ereignisverlauf_erstellen(
            ar_data, ar_b64, ev_data, ev_b64, ev_code)
        if event_log_id and zustand_kod == '00':
            self._post_event_response(event_log_id, zustand_kod)
        return True

    @staticmethod
    def _validate_event_sequence(event, current_event_display):
        '''
        Valida que la secuencia de eventos sea correcta (030 → 032 → 033).
        Retorna lista de mensajes de error; vacía si es válido.
        Trabaja con primitivos — reutilizable desde cualquier modelo.
        '''
        event_codes = dict(EVENT_CODES)
        errors = []
        if event == '030' and current_event_display not in ('02', '04', False, '67', 'other'):
            errors.append('- Tiene el evento %s.' % event_codes.get(current_event_display, '-'))
        if event == '032' and current_event_display != '030':
            errors.append('- El evento previo debe ser %s.' % event_codes.get('030', '-'))
        if event == '033' and current_event_display != '032':
            errors.append('- El evento previo debe ser %s.' % event_codes.get('032', '-'))
        return errors

    # ── Hooks — cada modelo concreto sobreescribe los que apliquen ────────────

    def _get_cufe_for_status(self):
        '''Retorna el CUFE/UUID a usar para consultas de estado en la DIAN.'''
        raise NotImplementedError(
            '%s debe implementar _get_cufe_for_status()' % self._name)

    def _get_event_receiver(self):
        '''Retorna el res.partner receptor del evento (contraparte del documento).'''
        raise NotImplementedError(
            '%s debe implementar _get_event_receiver()' % self._name)

    def _get_event_user_partner(self):
        '''
        Retorna el res.partner del usuario que ejecuta el evento.
        Implementación por defecto: usa ev_fe_user_id o el usuario activo.
        '''
        return self.ev_fe_user_id and self.ev_fe_user_id.partner_id or self.env.user.partner_id

    def _get_event_claim(self):
        '''
        Retorna (dian_code, name) del concepto de rechazo para el evento 031.
        Lanza ValidationError si no está configurado.
        '''
        raise NotImplementedError(
            '%s debe implementar _get_event_claim()' % self._name)

    def _reshnugnsdaten_abrufen(self):
        '''
        Retorna dict con los datos del documento referenciado para el evento:
        {'ID': str, 'UUID': str, 'UUID_Algoritm': str, 'DocTypeCode': str}
        '''
        raise NotImplementedError(
            '%s debe implementar _reshnugnsdaten_abrufen()' % self._name)

    def _get_edi_filenames(self, file_type):
        '''
        Retorna el nombre de archivo para el ZIP/AR/AD del evento.
        file_type: 'ar' | 'ad' | 'zip'
        '''
        raise NotImplementedError(
            '%s debe implementar _get_edi_filenames()' % self._name)

    def _xml_soap_werte_erhalten(self):
        '''Retorna el dict de valores para construir el envelope SOAP del evento.'''
        raise NotImplementedError(
            '%s debe implementar _xml_soap_werte_erhalten()' % self._name)

    def _bring_anfrage_unterzeichnet(self, exe_env, wsdl, art, uuid):
        '''Retorna el XML SOAP firmado para la solicitud de consulta de estado.'''
        raise NotImplementedError(
            '%s debe implementar _bring_anfrage_unterzeichnet()' % self._name)

    def versandlog_erstellen(self, anfrageart, daten_antwort, anfrage, exe_env):
        '''
        Registra el log de envío del evento.
        Implementación por defecto: no-op.
        account.move crea registros en edi.document.log.
        '''
        pass

    def ereignisverlauf_erstellen(self, werte=False, ar_b64=False,
                                  ev_data=False, ev_b64=False, event_code=False):
        '''
        Crea el registro de historial del evento.
        Implementación por defecto: no-op (retorna None).
        account.move crea registros en history.dian.event.
        '''
        return None

    def _post_event_response(self, event_log_id, zustand_kod):
        '''
        Postprocesado tras registrar un evento exitoso (zustand_kod == "00"):
        generación del documento adjunto (AttachedDocument) y envío de correo.
        Implementación por defecto: no-op.
        account.move genera el AD y envía el correo.
        '''
        pass
