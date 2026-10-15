# -*- coding: utf-8 -*-

import time
import logging
import json
import traceback
from lxml import etree
from sys import exc_info
from traceback import format_exception
from datetime import datetime, timedelta
from . import ir_sentences as satz
from requests import post, exceptions
from base64 import b64encode, b64decode
from pytz import timezone

from odoo import api, fields, models, _, tools, Command
from odoo.modules.registry import Registry
from odoo.fields import Domain
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang, format_date, get_lang

_logger = logging.getLogger(__name__)

TYPE_DOC_NAME = {
    'invoice': 'Factura',
    'credit': 'Nota Crédito',
    'debit': 'Nota Débito'
}

URL_CUFE = {
    'hab': 'https://catalogo-vpfe-hab.dian.gov.co'
    '/document/searchqr?documentkey=CUFE',
    'prod': 'https://catalogo-vpfe.dian.gov.co'
    '/document/searchqr?documentkey=CUFE'
}

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

EDI_OPERATION_TYPE = [
    ('10', 'Estandar'),
    ('09', 'AIU'),
    ('11', 'Mandatos'),
    ('12', 'Transporte'),
    # ('14', 'Notarios'),
    # ('15', 'Compra Divisas'),
    # ('16', 'Venta Divisas'),
    ('20', 'Nota Crédito que referencia una factura electrónica'),
    ('22', 'Nota Crédito sin referencia a facturas'),
    # ('23', 'Nota Crédito para facturación electrónica V1 (Decreto 2242)'),
    ('30', 'Nota Débito que referencia una factura electrónica'),
    ('32', 'Nota Débito sin referencia a facturas'),
    # ('33', 'Nota Débito para facturación electrónica V1 (Decreto 2242)')
]

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


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_einv_warning(self):
        warn_remaining = False
        inactive_resolution = False
        sequence_id = self.journal_id.sequence_id

        if sequence_id.edi_resolution_control:
            remaining_numbers = self.journal_id.remaining_numbers
            remaining_days = self.journal_id.remaining_days
            date_range = self.env['ir.sequence.date_range'].search(
                [('sequence_id', '=', sequence_id.id),
                 ('active_resolution', '=', True)])
            today = datetime.strptime(
                str(fields.Date.today(self)), '%Y-%m-%d')
            if date_range:
                date_range.ensure_one()
                date_to = datetime.strptime(
                    str(date_range.date_to), '%Y-%m-%d')
                days = (date_to - today).days
                numbers = date_range.number_to - date_range.number_next_actual
                if numbers < remaining_numbers or days < remaining_days:
                    warn_remaining = True
            else:
                inactive_resolution = True
        self.is_inactive_resolution = inactive_resolution
        self.fe_warning = warn_remaining

    fe_warning = fields.Boolean('Advertir por rangos reolución?',
                                compute='_get_einv_warning',
                                store=False)
    is_inactive_resolution = fields.Boolean('Advertir Resolución Inactiva?',
                                            compute='_get_einv_warning',
                                            store=False)
    fe_invoice_name = fields.Char('Factura Electrónica',
                                help='Consecutivo de la factura '
                                'electrónica publicada en la DIAN.',
                                readonly=True,
                                copy=False)
    fe_datetime_invoice = fields.Datetime('Fecha validación',
                                help='Campo técnico utilizado para '
                                'almacenar la hora de validación de '
                                'la factura.',
                                copy=False)
    fe_type = fields.Selection(
        [('01', 'Factura de venta'),
         ('02', 'Factura de exportación'),
         ('03', 'Documento electrónico de transmisión - tipo 03'),
         ('04', 'Factura electrónica de Venta - tipo 04'), ],
        'Tipo fac. electrónica',
        required=True,
        default='01')
    fe_operation_type = fields.Selection(EDI_OPERATION_TYPE,
                                'Operation Type',
                                default='10',
                                required=True)
    fe_payment_option_id = fields.Many2one('dian.payment.option',
                                'Opción de pago',
                                default=lambda self: self.env.ref(
                                    'l10n_co_data_bloodo.payment_option_1',
                                    raise_if_not_found=False))
    fe_is_direct_payment = fields.Boolean('Direct Payment from Colombia',
                                compute='_compute_fe_is_direct_payment')
    fe_mandante_id = fields.Many2one('res.partner',
                                'Mandante')
    fe_cufe_cude_ref = fields.Char('CUFE/CUDE',
                                readonly=True,
                                copy=False,
                                tracking=True)
    fe_url = fields.Char('Url',
                        copy=False)
    fe_cufe_cude_uncoded = fields.Char('CUFE/CUDE uncoded',
                                copy=False,
                                tracking=True)
    fe_ssc_uncoded = fields.Char('SSC uncoded',
                                copy=False)
    fe_ssc = fields.Char('SSC',
                        copy=False)
    fe_qr_image = fields.Binary('QR',
                        copy=False)
    fe_qr_data = fields.Text('Datos QR',
                        copy=False)

    is_external_invoice = fields.Boolean('Factura externa?',
                                copy=False)
    name_ei_ref = fields.Char('N° Factura (Ref)',
                        copy=False)
    uuid_ei_ref = fields.Char('CUFE (Ref)',
                        copy=False)
    issue_date_ei_ref = fields.Date('Fecha (Ref)',
                                copy=False)
    operation_type_ei_ref = fields.Selection(EDI_OPERATION_TYPE,
                                'Tipo de operación (Ref)',
                                copy=False)
    fe_type_ei_ref = fields.Selection(
        [('01', 'Factura de venta'),
         ('02', 'Factura de exportación'),
         ('03', 'Documento electrónico de transmisión - tipo 03'),
         ('04', 'Factura electrónica de Venta - tipo 04'),
         ('20', 'Tiquete POS'),
         ('25', 'Boleta de ingreso a cine'),
         ('27', 'Boleta de ingreso a espectaculos púbicos'),
         ('30', 'Documento en juegos localizados y no localizados'),
         ('35', 'Tiquete transporte de pasajeros terrestre'),
         ('40', 'Documento para control de peajes'),
         ('45', 'Extracto expedido por sociedades financieras y fondos'),
         ('50', 'Tiquete transporte aéreo de pasajeros'),
         ('55', 'Documento de bolsa de valores, agropecuaria y otros comodities'),
         ('60', 'Documento de servicios públicos y domiciliarios'),
         ('93', 'Nota Débito al Documento Equivalente'),
         ('94', 'Nota Crédito al Documento Equivalente'),
         ('07', 'Contingencia por parte del emisor (Doc. Eq.)'),
         ('08', 'Contingencia por parte DIAN (Doc. Eq.)'),
         ('91', 'Nota Crédito'),
         ('92', 'Nota Débito'),
         ('96', 'Eventos (ApplicationResponse)'), ],
        'Ref Type',
        required=True,
        default='01')

    fe_correction_id = fields.Many2one('dian.discrepancy.response',
                                'Concepto de corrección',
                                copy=False)
    type_note = fields.Selection([('debit', 'Nota Débito'),
                                  ('credit', 'Nota Crédito')],
                                'Tipo de nota')
    credit_note_ids = fields.One2many('account.move',
                                'reversed_entry_id',
                                'Notas crédito',
                                copy=False)
    credit_note_count = fields.Integer('Número de notas crédito',
                                compute='_compute_credit_count')

    # DIAN DOC
    is_einvoicing_journal = fields.Boolean('Diario con fac electrónica',
                                related='journal_id.is_einvoicing')
    fe_pdf_fname = fields.Char('Nombre Pdf',
                        copy=False)
    fe_pdf_file = fields.Binary('Rep gráfica (Pdf)',
                        copy=False)
    fe_xml_fname = fields.Char('Nombre XML',
                        copy=False)
    fe_xml_file = fields.Binary('XML',
                        copy=False)
    fe_ad_fname = fields.Char('Nombre Attached',
                        copy=False)
    fe_ad_file = fields.Binary('AttachedDocument',
                        copy=False)
    fe_zip_id = fields.Many2one(
        comodel_name='ir.attachment',
        string="ZIP Attachment",
        compute=lambda self: self._compute_linked_attachment_id('fe_zip_id', 'fe_zip_file'),
        depends=['fe_zip_file']
    )
    fe_zip_fname = fields.Char('Nombre Zip',
                        copy=False)
    fe_zip_file = fields.Binary('ZIP',
                        copy=False)
    fe_ar_fname = fields.Char('Nombre ApplicationResponse',
                        copy=False)
    fe_ar_file = fields.Binary('ApplicationResponse',
                        copy=False)
    fe_zip_key = fields.Char('ZipKey',
                        copy=False)
    # Response
    fe_state = fields.Char('Código estado DIAN',
                        default=False,
                        copy=False)
    fe_state_msg = fields.Char('Estado DIAN',
                        default=False,
                        copy=False,
                        tracking=True)

    fe_response = fields.Text('Respuesta DIAN',
                        copy=False)
    mail_sent = fields.Boolean('Correo enviado?',
                        copy=False)
    # LOG
    fe_log_ids = fields.One2many('edi.document.log',
                                'move_id',
                                'Edi log',
                                copy=False)
    # SUPPLIER EI
    is_supplier_ei = fields.Boolean('FE proveedor',
                                default=False,
                                copy=False)
    way_to_pay = fields.Selection([('credit', 'Credit'),
                                   ('cash', 'Cash')],
                                'Forma de pago',
                                compute='_compute_way_to_pay',
                                store=True)
    ie_event_status = fields.Char('Código de estado evento',
                                copy=False)
    ie_event_history_ids = fields.One2many('history.dian.event',
                                'move_id',
                                'Historial eventos',
                                copy=False,
                                help='Histórico de eventos')
    ie_event_active_id = fields.Many2one('history.dian.event',
                                'Evento activo',
                                compute='_compute_event_active_id',
                                copy=False)
    ie_event_active_date = fields.Datetime('Fecha de registro del evento',
                                copy=False)
    ie_claim_id = fields.Many2one('dian.claim.concept',
                                'Concepto de rechazo',
                                copy=False)
    ie_event_display = fields.Selection(EVENT_CODES,
                                'Estado evento',
                                copy=False,
                                help='Evento activo de la '
                                'fac. electrónica, consulta el estado '
                                'para mantenerla actualizada.')
    ev_fe_state = fields.Char('Estado de envío del evento',
                        default=False,
                        copy=False,
                        help='Código de estado del evento '
                        'entregado a la DIAN')
    ev_fe_response = fields.Text('Respuesta de entrega evento',
                                copy=False,
                                help='Mensaje de respuesta de la '
                                'entrega del evento. Aquí puede ver la '
                                'lista de validaciones para corregir '
                                'si el evento ha sido rechazado.')
    ev_check_date = fields.Date('Fecha consulta evento DIAN',
                                help='Fecha de la ultima consulta del estado del evento DIAN')
    fe_send_later = fields.Boolean('Enviar después',
                                help='La factura electrónica será enviada '
                                'posteriormente a través de un proceso en segundo plano '
                                'que se ejecuta cada 15 minutos.',
                                default=False,
                                tracking=True)
    fe_period_start = fields.Date('Fecha inicio periodo',
                                help='Fecha inicio del periodo de facturación')
    fe_period_end = fields.Date('Fecha fin periodo',
                                help='Fecha fin del periodo de facturación')
    remmision_ref = fields.Char('Remisiones de cliente',
                                help='Agregue las remisiones del cliente separadas por punto y coma (;)',
                                copy=False,
                                tracking=True)
    ref2 = fields.Char('Referencia de cliente 2',
                       help='Agregue los documentos de recepción asociados a la factura, separados por punto y coma (;)',
                       copy=False,
                       tracking=True)
    ev_fe_user_id = fields.Many2one('res.users',
                                'Usuario evento',
                                help='Usuario que realizó el último evento en la factura electrónica',
                                copy=False)

    def _compute_event_active_id(self):
        for record in self:
            event_id = record.ie_event_history_ids.filtered(
                lambda e: e.ev_active
            )
            record.ie_event_active_id = event_id \
                and event_id[0].id \
                    or False

    @api.depends('move_type', 'invoice_date',
                 'invoice_date_due', 'issue_date_ei_ref')
    def _compute_way_to_pay(self):
        for record in self:
            date = record.issue_date_ei_ref or record.invoice_date or False
            date_due = record.invoice_date_due
            pay = 'cash'
            if date and date_due:
                if date < date_due:
                    pay = 'credit'
            record.way_to_pay = pay

    def _qrcode_erhalten(self, NumFac, FecFac, HorFac, NitFac, DocAdq, ValFac,
                         ValIva, ValOtroIm, ValTolFac, UUID, url, type_doc):
        qr_data = 'NA'
        if NumFac:
            qr_data = 'NumFac: {}'.format(NumFac or 'NO_VALIDADA')
            qr_data += '\nFecFac: {}'.format(FecFac or '-')
            qr_data += '\nHorFac: {}'.format(HorFac or '-')
            qr_data += '\nNitFac: {}'.format(NitFac or '-')
            qr_data += '\nNitAdq: {}'.format(DocAdq or '-')
            qr_data += '\nValFac: {:.2f}'.format(ValFac)
            qr_data += '\nValIva: {:.2f}'.format(ValIva)
            qr_data += '\nValOtroIm: {:.2f}'.format(ValOtroIm)
            qr_data += '\nValTolFac: {:.2f}'.format(ValTolFac)
            qr_data += '\n{}: {}'.format(
                type_doc == 'invoice' and 'CUFE' or 'CUDE',
                UUID or '-'
            )
            qr_data += '\nQRCode: {}'.format(url or '-')

        qr_image = satz.qrcode_erzeugen(qr_data)
        return {
            'qr_image': qr_image,
            'qr_data': qr_data
        }

    @api.depends('invoice_date_due', 'date')
    def _compute_fe_is_direct_payment(self):
        for rec in self:
            rec.fe_is_direct_payment = (rec.date == rec.invoice_date_due) \
                and rec.company_id.country_id.code == 'CO' \
                    and rec.is_einvoicing_journal

    @api.depends('credit_note_ids')
    def _compute_credit_count(self):
        credit_data = self.env['account.move'].read_group(
            [('reversed_entry_id', 'in', self.ids)],
            ['reversed_entry_id'],
            ['reversed_entry_id'])
        data_map = {
            datum['reversed_entry_id'][0]:
                datum['reversed_entry_id_count'] for datum in credit_data
        }
        for inv in self:
            inv.credit_note_count = data_map.get(inv.id, 0.0)

    def action_view_credit_notes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Notas Crédito'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('reversed_entry_id', '=', self.id)],
        }

    def _get_sequence(self):
        '''
            Return the sequence to be used during
             the post of the current move.
            :return: An ir.sequence record or False.
        '''
        res = super(AccountMove, self)._get_sequence()

        journal = self.journal_id
        if self.move_type == 'out_invoice' and not self.type_note:
            return journal.sequence_id
        elif self.move_type == 'out_refund' and self.type_note == 'credit':
            return journal.refund_sequence_id
        elif self.move_type == 'out_invoice' and self.type_note == 'debit':
            return journal.debit_note_sequence_id
        return res

    def _post(self, soft=True):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(
                    _('La factura [id: %s] no se encuentra en estado borrador '
                      'y no se puede publicar. \nPor favor, refresque la '
                      'página para actualizar la información.', record.id))
        res = super(AccountMove, self)._post(soft)
        for record in self:
            if record.move_type in ('out_invoice', 'out_refund') and \
               record.company_id.type_einvoicing == 'edi_dir' and \
               record.journal_id.is_einvoicing:
                if record.name and record.name != '/':
                    record.fe_invoice_name = record.name
                record.xml_datei_erhalten()
            #  PARA ENVIAR Y CONSULTAR ESTADO DIAN
                if len(self) == 1 and not record.fe_send_later:
                    # if self.send_invoice_to_dian == '0':
                    if record.fe_type in ('01', '02', '03'):
                        # Factura
                        record.rechnung_senden()
                    elif record.invoice_type_code == '04' and not record.partner_id.dian_not_send_email:
                        record.action_send_mail()
            elif record.move_type in ('in_invoice', 'in_refund') \
                and record.company_id.type_support_doc == 'edi_dir' \
                    and record.journal_id.is_einvoicing:
                if record.name and record.name != '/':
                    record.fe_invoice_name = record.name
                record.xml_datei_erhalten_ds()
            #  PARA ENVIAR Y CONSULTAR ESTADO DIAN
                if len(self) == 1 and not record.fe_send_later:
                    # Documento soporte
                    record.rechnung_senden()
        return res

    def xml_datei_erhalten(self):
        self.ensure_one()
        type_doc = self._get_type_document()
        xml_str = self._get_xml_edi_file(type_doc)
        xml_fname = self.fe_xml_fname \
            and self.fe_xml_fname \
                or self._get_edi_filenames(type_doc)
        zip_fname = self.fe_zip_fname \
            and self.fe_zip_fname \
                or self._get_edi_filenames('zip')
        ar_fname = self.fe_ar_fname \
            and self.fe_ar_fname \
                or self._get_edi_filenames('ar')
        ad_fname = self.fe_ad_fname \
            and self.fe_ad_fname \
                or self._get_edi_filenames('ad')

        xml_file = b64encode(xml_str)
        data_to_zip = [(xml_fname, xml_file)]
        zip_file = b64encode(satz.get_zipped_file(data_to_zip))
        if self.company_id.fname_pdf_same_xml:
            name_pdf = xml_fname.replace('.xml', '.pdf')
        else:
            name_pdf = f"{TYPE_DOC_NAME.get(type_doc, _('Documento'))} {self.name}.pdf"

        self.write({
            'fe_xml_fname': xml_fname,
            'fe_zip_fname': zip_fname,
            'fe_ar_fname': ar_fname,
            'fe_ad_fname': ad_fname,
            'fe_pdf_fname': name_pdf,
        })
        self.write({
            'fe_xml_file': xml_file,
            'fe_zip_file': zip_file,
        })

    def _get_mail_template(self):
        """
        :return: the correct mail template based on the current move type
        """
        if len(self.ids) == 1 and self.is_einvoicing_journal:
            return self.env.ref('l10n_co_bloodo.dian_email_template')
        else:
            return super(AccountMove, self)._get_mail_template()

    def action_invoice_sentX(self):
        '''
            Open a window to compose an email, with the edi invoice template
            message loaded by default
        '''
        self.ensure_one()
        if self.is_einvoicing_journal:
            template = self.env.ref('l10n_co_bloodo.dian_email_template',
                                    raise_if_not_found=False)
        else:
            template = self.env.ref('account.email_template_edi_invoice',
                                    raise_if_not_found=False)
        attach_ids = []
        zip_attachment_file = False
        if self.fe_zip_file:
            zip_attachment_file = self.env['ir.attachment'].create({
                'name': self.fe_zip_fname,
                'type': 'binary',
                'datas': self.fe_zip_file,
            })
        if zip_attachment_file:
            attach_ids.append(zip_attachment_file.id)
        if attach_ids:
            template.attachment_ids = [(6, 0, attach_ids)]
        lang = False
        if template:
            lang = template._render_lang(self.ids)[self.id]
        if not lang:
            lang = get_lang(self.env).code
        compose_form = self.env.ref('account.account_invoice_send_wizard_form',
                                    raise_if_not_found=False)
        ctx = dict(
            default_model='account.move',
            default_res_id=self.id,
            # For the sake of consistency we need a default_res_model if
            # default_res_id is set. Not renaming default_model as it can
            # create many side-effects.
            default_res_model='account.move',
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            mark_invoice_as_sent=True,
            custom_layout='mail.mail_notification_layout_with_responsible_signature',
            model_description=self.with_context(lang=lang).type_name,
            force_email=True
        )
        return {
            'name': _('Send Invoice'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.invoice.send',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    def _get_type_document(self):
        '''
            Return: 'invoice' or 'credit' or 'debit'
        '''
        self.ensure_one()
        if self.move_type == 'out_invoice' and not self.type_note:
            return 'invoice'
        elif self.move_type == 'out_refund' and self.type_note != 'debit':
            return 'credit'
        elif self.move_type == 'out_invoice' and self.type_note == 'debit':
            return 'debit'
        else:
            return False

    def _get_edi_filenames(self, type_doc=''):
        '''
            Calculates the name of the e-incoice files.
            Chapter. 6.7, 6.8
            - 'invoice' --> fvnnnnnnnnnnpppaadddddddd.xml
            - 'credit'  --> ncnnnnnnnnnnpppaadddddddd.xml
            - 'debit'   --> ndnnnnnnnnnnpppaadddddddd.xml
            - 'ar'      --> arnnnnnnnnnnpppaadddddddd.xml
            - 'ad'      --> adnnnnnnnnnnpppaadddddddd.xml
            - 'zip'     --> znnnnnnnnnnpppaadddddddd.zip
        '''
        self.ensure_one()
        seq_map = {
            'invoice': ('fv', 'dian.fv.sent', 'fv_sent'),
            'credit': ('nc', 'dian.nc.sent', 'nc_sent'),
            'debit': ('nd', 'dian.nd.sent', 'nd_sent'),
            'ar': ('ar', 'dian.ar.sent', 'ar_sent'),
            'ad': ('ad', 'dian.ad.sent', 'ad_sent'),
            'zip': ('z', 'dian.zip.sent', 'zip_sent'),
        }
        prefix = ''
        nnnnnnnnnn = ''
        aa = ''
        dddddddd = ''
        ext = '.xml'
        if type_doc not in seq_map:
            raise ValidationError(
                _('ERROR: No se puede definir el tipo de documento '
                  'electrónico de este asiento. \nId asiento: %s\nTipo documento: %s', self.id, type_doc))
        if not self.company_id.partner_id.vat:
            raise ValidationError(
                _('El documento de identificación de %s no está establecido. \n',
                  self.company_id.partner_id.name))
        
        prefix, seq_code, seq_field = seq_map[type_doc]
        ext = '.zip' if type_doc == 'zip' else '.xml'

        seq_id = self.sudo().company_id._get_or_create_sequence_dian_sent(seq_code, seq_field)
        seq_number = seq_id.next_by_id() if seq_id else False
        if not seq_number:
            raise ValidationError(
                _('No se pudo obtener el número de secuencia para el tipo de documento %s. \n'
                  'Por favor, revise la configuración de secuencias de su compañía.\n %s', type_doc, self.company_id.name))
        
        nnnnnnnnnn = self.company_id.partner_id.vat.zfill(10)
        ppp = '000'
        dddddddd = int(seq_number)
        aa = fields.Datetime.context_timestamp(self,
                                               fields.Datetime.now()
                                               ).strftime('%y')
        dddddddd = '{:08x}'.format(dddddddd).upper()
        nnnnnnnnnnpppaadddddddd = nnnnnnnnnn + ppp + aa + dddddddd
        return prefix + nnnnnnnnnnpppaadddddddd + ext

    # Not used
    def get_name_type_document(self):
        self.ensure_one()
        type_document = self._get_type_document()
        name_doc = ''
        if type_document == 'invoice':
            name_doc = _('Factura')
        elif type_document == 'credit':
            name_doc = _('Nota Crédito')
        elif type_document == 'debit':
            name_doc = _('Nota Débito')
        return name_doc

    def _get_xml_edi_file(self, type_doc=''):
        self.ensure_one()
        if type_doc == 'invoice':
            doc_values = self._get_values_fv_edi(type_doc)
            doc_template = 'Invoice'
        elif type_doc == 'credit':
            doc_values = self._get_values_nc_edi(type_doc)
            doc_template = 'CreditNote'
        elif type_doc == 'debit':
            doc_values = self._get_values_nd_edi(type_doc)
            doc_template = 'DebitNote'
        else:
            raise ValidationError(
                _('ERROR: No se puede definir el tipo de '
                  'documento electrónico de este asiento'))
        unsigned_xml = satz.render_xml_edi(doc_values,
                                           doc_template)
        xml_mit_signatur = satz.xml_mit_signatur_erhalten(
            unsigned_xml,
            self.company_id.signature_policy_url,
            self.company_id.signature_policy_description,
            self.company_id.signature_policy_file,
            self.company_id.certificate_file,
            self.company_id.certificate_password,
            doc_values.get('IssueDate'),
            doc_values.get('IssueTime'))
        return xml_mit_signatur

    def _get_values_fv_edi(self, type_doc=False):
        self.ensure_one()
        werte = self._datenwerte_erhalten(type_doc)
        werte['CustomizationID'] = self.fe_operation_type
        # active_resolution = self._aktive_auflosung_erhalten()
        # werte['InvoiceControl'] = active_resolution
        werte['InvoiceTypeCode'] = self.fe_type
        # werte['InvoiceLines'] = self._linienwerte_erhalten()
        return werte

    def _get_values_nc_edi(self, type_doc=''):
        self.ensure_one()
        werte = self._datenwerte_erhalten(type_doc)
        if self.fe_operation_type == '20' and self.is_external_invoice:
            billing_reference = {'ID': self.name_ei_ref,
                                 'UUID': self.uuid_ei_ref,
                                 'IssueDate': self.issue_date_ei_ref,
                                 'CustomizationID': self.operation_type_ei_ref}
        elif self.fe_operation_type != '22' and self.reversed_entry_id:
            billing_reference = self._get_billing_reference()
        else:
            billing_reference = False
        # 20 Nota Crédito que referencia una factura electrónica.
        # 22 Nota Crédito sin referencia a facturas*.
        # 23 Nota Crédito para facturación electrónica V1 (Decreto 2242).
        if billing_reference:
            werte['CustomizationID'] = '20'
            self.fe_operation_type = '20'
        elif self.fe_operation_type == '22':
            werte['CustomizationID'] = '22'
            self.fe_operation_type = '22'
            billing_reference = {'ID': False,
                                 'UUID': False,
                                 'IssueDate': False,
                                 'CustomizationID': False}
        else:
            raise ValidationError(
                _('No se puede enviar una nota crédito que no está '
                  'relacionada con una factura, por favor cambie el '
                  'Tipo de operación en el documento.'))
        # 91 Nota Crédito
        werte['CreditNoteTypeCode'] = '91'
        werte['BillingReference'] = billing_reference
        werte['DiscrepancyReferenceID'] = billing_reference['ID']
        werte['DiscrepancyResponseCode'] = self.fe_correction_id.dian_code
        werte['DiscrepancyDescription'] = self.fe_correction_id.name
        # self._linienwerte_erhalten()
        werte['CreditNoteLines'] = werte['InvoiceLines']
        # ACTUALIZACION V1.8 AGOSTO 2021
        werte['Prefix_nc'] = self.get_prefix_doc('nc')
        return werte

    def get_prefix_doc(self, type_note='inv'):
        self.ensure_one()
        prefix = ''
        if type_note == 'inv':
            prefix = self.journal_id.sequence_id.prefix
        elif type_note == 'nc':
            prefix = self.journal_id.refund_sequence_id.prefix
        elif type_note == 'nd':
            prefix = self.journal_id.debit_note_sequence_id.prefix
        return prefix

    # def _get_debit_note_values(self):
    def _get_values_nd_edi(self, type_doc=''):
        self.ensure_one()
        werte = self._datenwerte_erhalten(type_doc)
        if self.fe_operation_type == '30' and self.is_external_invoice:
            billing_reference = {'ID': self.name_ei_ref,
                                 'UUID': self.uuid_ei_ref,
                                 'IssueDate': self.issue_date_ei_ref,
                                 'CustomizationID': self.operation_type_ei_ref}
        elif self.fe_operation_type != '32' and self.debit_origin_id:
            billing_reference = self._get_billing_reference()
        else:
            billing_reference = False
        # 30 Nota Débito que referencia una factura electrónica.
        # 32 Nota Débito sin referencia a facturas *.
        # 33 Nota Débito para facturación electrónica V1 (Decreto 2242).
        if billing_reference:
            werte['CustomizationID'] = '30'
            self.fe_operation_type = '30'
        elif self.fe_operation_type == '32':
            werte['CustomizationID'] = '32'
            self.fe_operation_type = '32'
            billing_reference = {'ID': False,
                                 'UUID': False,
                                 'IssueDate': False,
                                 'CustomizationID': False}
        else:
            raise ValidationError(
                _('No se puede enviar una nota débito que no está '
                  'relacionada con una factura, por favor cambie el '
                  'Tipo de operación en el documento.'))
        # 92 Nota Débito
        # TODO 2.0: DebitNoteTypeCode no existe en DebitNote
        # werte['DebitNoteTypeCode'] = '92'
        werte['BillingReference'] = billing_reference
        werte['DiscrepancyReferenceID'] = billing_reference['ID']
        werte['DiscrepancyResponseCode'] = self.fe_correction_id.dian_code
        werte['DiscrepancyDescription'] = self.fe_correction_id.name
        # self._linienwerte_erhalten()
        werte['DebitNoteLines'] = werte['InvoiceLines']
        werte['Prefix_nd'] = self.get_prefix_doc('nd')
        return werte

    def _datenwerte_erhalten(self, type_doc=''):
        self.ensure_one()
        active_resolution = self._aktive_auflosung_erhalten()
        supplier = self.company_id.partner_id
        customer = self.partner_id
        IdSoftware = self.company_id.software_id
        AcSupplierParty = satz.escape_xml(supplier._personendetails_erhalten())
        AcCustomerParty = satz.escape_xml(customer._personendetails_erhalten())
        trm_data = self._get_payment_exchange_rate('fe')
        trm = trm_data.get('SourceCurrencyBaseRate', 1)
        InvoiceLines = self._linienwerte_erhalten(trm)
        edi_taxes = self._header_steuern_erhalten(trm, InvoiceLines)
        edi_taxes = self._validate_taxes(edi_taxes, InvoiceLines)
        taxable_base = self._get_taxable_base(InvoiceLines)
        self.fe_datetime_invoice = datetime.now()
        date_format = str(self.create_date)[0:19]
        create_date = datetime.strptime(date_format, '%Y-%m-%d %H:%M:%S')
        create_date = create_date.replace(tzinfo=timezone('UTC'))
        notes = self._notizen_mitbringen()

        NumFac = self.name
        FecFac = self.invoice_date.strftime('%Y-%m-%d')
        HorFac = create_date.astimezone(
            timezone('America/Bogota')).strftime('%H:%M:%S-05:00')
        ValFac = self.amount_untaxed * trm
        ValImp1 = edi_taxes['TaxesTotal'].get('01', {}).get('total', 0)
        ValImp2 = edi_taxes['TaxesTotal'].get('04', {}).get('total', 0)
        ValImp3 = edi_taxes['TaxesTotal'].get('03', {}).get('total', 0)
        ValOtroIm = ValImp2 + ValImp3
        # ValTot = ValFac + ValImp1 + ValImp2 + ValImp3
        ValTot = ValFac + sum([x.get('total', 0) for x in edi_taxes['TaxesTotal'].values()])
        NitFE = supplier.vat
        NumAdq = customer.vat
        ClTec_SoftPIN = False
        exe_env = self.company_id.target_environment_id

        if self.move_type == 'out_invoice' and not self.type_note:
            ClTec_SoftPIN = active_resolution['technical_key']
        else:
            ClTec_SoftPIN = self.company_id.software_pin

        cufe_cude = satz.get_cufe_cude([NumFac, FecFac, HorFac,
                                        str('{:.2f}'.format(ValFac)),
                                        '01', str('{:.2f}'.format(ValImp1)),
                                        '04', str('{:.2f}'.format(ValImp2)),
                                        '03', str('{:.2f}'.format(ValImp3)),
                                        str('{:.2f}'.format(ValTot)),
                                        NitFE, NumAdq, ClTec_SoftPIN,
                                        exe_env])
        sscode = satz.ssc_erhalten(IdSoftware,
                                   self.company_id.software_pin,
                                   NumFac)
        if exe_env == '1':
            QRCodeURL = DIAN['catalogo']
        else:
            QRCodeURL = DIAN['catalogo-hab']
        QRCodeURL = QRCodeURL.format(cufe_cude['uuid'])

        if self.fe_type == '02':
            if not self.invoice_incoterm_id:
                raise UserError(
                    _('Es necesario el Incoterm para esta '
                      'factura tipo exportación.'))
            elif not self.invoice_incoterm_id.name \
                    or not self.invoice_incoterm_id.code:
                raise UserError(
                    _('Incoterm no está correctamente parametrizado.\n'
                      'id: %s', self.invoice_incoterm_id.id))

        # El valor a pagar puede verse afectado, por anticipos,
        # y descuentos y cargos a nivel de factura
        PayableAmount = ValTot

        qrcode_data = self._qrcode_erhalten(
            NumFac=NumFac, FecFac=FecFac, HorFac=HorFac, NitFac=NitFE,
            DocAdq=NumAdq, ValFac=ValFac, ValIva=ValImp1, ValOtroIm=ValOtroIm,
            ValTolFac=ValTot, UUID=cufe_cude['uuid'], url=QRCodeURL,
            type_doc=type_doc)

        self.write({
            'fe_url': QRCodeURL,
            'fe_cufe_cude_uncoded': cufe_cude['uuid_uncoded'],
            'fe_cufe_cude_ref': cufe_cude['uuid'],
            'fe_ssc_uncoded': sscode['SSC_Uncoded'],
            'fe_ssc': sscode['SSC'],
            'fe_qr_image': qrcode_data['qr_image'],
            'fe_qr_data': qrcode_data['qr_data'],
        })

        return {
            # Resolución
            'InvoiceAuthorization': active_resolution['resolution_number'],
            'StartDate': active_resolution['date_from'],
            'EndDate': active_resolution['date_to'],
            'Prefix': active_resolution['prefix'],
            'From': active_resolution['number_from'],
            'To': active_resolution['number_to'],
            # Proveedor Tecnológico
            'ProviderIDschemeID': supplier.l10n_co_verification_code,
            'ProviderIDschemeName': \
                supplier.l10n_latam_identification_type_id.dian_code,
            'ProviderID': NitFE,

            'NitAdquiriente': NumAdq,
            'SoftwareID': IdSoftware,
            'SoftwareSecurityCode': sscode['SSC'],
            'QRCodeURL': QRCodeURL,
            'ProfileExecutionID': exe_env,
            'ID': NumFac,
            'UUID': cufe_cude['uuid'],
            'IssueDate': FecFac,
            'IssueTime': HorFac,
            'Notes': notes,
            'LineCountNumeric': len(
                self.invoice_line_ids.filtered(
                    lambda ln: ln.display_type == 'product')),
            'PeriodStartDate': self.fe_period_start,
            'PeriodEndDate': self.fe_period_end,
            'DocumentCurrencyCode': 'COP', # self.currency_id.name,
            'Delivery': {}, # customer._get_address_partner_edi(),
            'DeliveryTerms': {
                'LossRiskResponsibilityCode': self.invoice_incoterm_id \
                    and self.invoice_incoterm_id.code or '',
                'LossRisk': self.invoice_incoterm_id.name or ''
            },
            'AccountingSupplierParty': AcSupplierParty,
            'AccountingCustomerParty': AcCustomerParty,
            # TODO: No esta completamente claro los datos de que tercero son
            'TaxRepresentativeParty': supplier._get_TaxRepresentativeParty(force_raise=True)[1],
            'PaymentMeansID': self._get_payment_mean_edi(),
            'PaymentMeansCode': self.fe_payment_option_id \
                and self.fe_payment_option_id.dian_code or '1',
            'DueDate': self.invoice_date_due,
            'PaymentExchangeRate': trm_data,
            'PaymentDueDate': self.invoice_date_due,
            'TaxesTotal': edi_taxes['TaxesTotal'],
            'WithTaxesTotal': edi_taxes['WithTaxesTotal'],
            'LineExtensionAmount': '{:.2f}'.format(ValFac),
            'TaxExclusiveAmount': '{:.2f}'.format(taxable_base),
            'TaxInclusiveAmount': '{:.2f}'.format(ValTot),
            'PayableAmount': '{:.2f}'.format(PayableAmount),
            'InvoiceLines': InvoiceLines,
            'OrderReference': satz.escape_xml(self._get_order_reference()),
            'ReceiptDocumentReference': satz.escape_xml(self.get_receipt_document_reference()),
        }

    def _get_order_reference(self):
        if self.ref:
            return {
                'order_id': self.ref
            }
        return {}

    def get_receipt_document_reference(self):
        out = []
        if self.ref2:
            refs = self.ref2.split(';')
            for ref in refs:
                out.append({'ID': ref.strip()})
        return out

    def _aktive_auflosung_erhalten(self):
        resolution_data = {}
        for range_id in self.journal_id.sequence_id.date_range_ids.filtered(
                lambda r: r.active_resolution):
            resolution_data = {
                'prefix': self.journal_id.sequence_id.prefix or '',
                'resolution_number': range_id.edi_resolution,
                'date_from': range_id.date_from,
                'date_to': range_id.date_to,
                'number_from': range_id.number_from,
                'number_to': range_id.number_to,
                'technical_key': self.journal_id.edi_technical_key
            }
        if not resolution_data:
            raise ValidationError(
                _('El diario no tiene una resolución de '
                  'facturación electrónica activa.'))
        return resolution_data

    def _validate_taxes(self, taxes, taxes_line):
        if '01' in taxes['TaxesTotal']:
            iva0 = list(filter(
                lambda l: '01' in l['TaxesTotal'] and
                '0.00' in l['TaxesTotal']['01']['taxes'],
                taxes_line.values()
            ))
            if not iva0:
                del taxes['TaxesTotal']['01']['taxes']['0.00']
            else:
                base_iva0 = sum([
                    x['TaxesTotal']['01']['taxes']['0.00']['base']
                    for x in iva0
                ])
                taxes['TaxesTotal']['01']['taxes']['0.00']['base'] = base_iva0
        return taxes

    def _get_taxable_base(self, taxes_line):
        iva = list(filter(lambda ln: '01' in ln['TaxesTotal'], 
                          taxes_line.values()))
        base_iva = 0
        for line in iva:
            base_iva += sum([y['base'] for y in line['TaxesTotal']['01']['taxes'].values()])
        return base_iva

    def _zieldok_erhalten(self):
        self.ensure_one()
        if self.move_type in ('out_invoice', 'out_refund'):
            exe_env = self.company_id.target_environment_id
            dok = 'ei'
        elif self.move_type in ('in_invoice', 'in_refund'):
            exe_env = self.company_id.ds_target_environment_id
            dok = 'sd'
        else:
            raise ValidationError(
                _('No se puede enviar un documento de tipo %s',
                  self.move_type))
        return exe_env, dok

    def _notizen_mitbringen(self):
        self.ensure_one()
        notes = []
        if self.move_type in ('out_invoice', 'out_refund') and self.remmision_ref:
            notes.append(self.remmision_ref)
        return notes

    def rechnung_senden(self):
        # action_sent_zipped_file
        self.ensure_one()
        msg1 = 'msg1'
        msg2 = 'msg2'
        b = 'http://schemas.datacontract.org/2004/07/UploadDocumentResponse'
        wsdl = DIAN['wsdl-hab']
        anfrageart = 'SendTestSetAsync'
        exe_env, dok = self._zieldok_erhalten()
        if exe_env == '1':
            anfrageart = 'SendBillSync'
            wsdl = DIAN['wsdl']
        anfrage = self._bring_anfrage_unterzeichnet(
            exe_env, wsdl, 'senden', dok)
        try:
            antwort = post(
                wsdl,
                headers={
                    'content-type': 'application/soap+xml;charset=utf-8'
                },
                data=anfrage
            )
            if antwort.status_code == 200:
                daten_antwort = satz.datenantwort_erhalten(antwort)
                # self.write({'state': 'gesendet'})
                self.versandlog_erstellen(
                    anfrageart, daten_antwort, anfrage, exe_env)
                if exe_env == '1':
                    self.die_antwort_verarbeiten(
                        daten_antwort,
                        exe_env=exe_env,
                        dok=dok
                    )
                else:
                    self.write({
                        'fe_zip_key': daten_antwort.get('zipkey', 'Error'),
                        # 'state': 'sent'
                    })
                    self.zip_status_erhalten()
            else:
                response_text = hasattr(antwort, 'text') and isinstance(antwort.text, str) and antwort.text.replace('><', '>\n<') or ''
                response_json = "{}"
                if satz.is_xml_ok(response_text):
                    response_json = satz.xml_to_json(response_text, attrs=True, simple=True)
                    response_text = satz.xml_to_json(response_text, attrs=False, simple=True)
                self.write({
                    'fe_state': 'OTRO',
                    'fe_state_msg': _('Ocurrió un problema en %s. '
                                      'Revisar respuesta desde pestaña Factura Electrónica',
                                      ANFRAGEART.get(anfrageart, 'Envío DIAN')),
                    'fe_response': 'Metodo: %s\n' \
                        'Estado: %s\n' \
                        'Razón: %s\n\n' \
                        '%s' % (anfrageart, antwort.status_code, antwort.reason, response_text),
                })
                self.versandlog_erstellen(
                    anfrageart,
                    {
                        'status_code': antwort.status_code,
                        'reason': antwort.reason,
                        'response_text': response_json,
                    },
                    anfrage,
                    exe_env
                )
        except Exception as e:
            e = exc_info()[0]
            tb = "".join(format_exception(*exc_info()))
            self.write({
                'fe_state': 'ERROR',
                'fe_state_msg': _('Error desconocido en %s. '
                                  'Revisar respuesta desde pestaña Factura Electrónica',
                                  ANFRAGEART.get(anfrageart, 'Envío DIAN')),
                'fe_response': _('Error desconocido en metodo %s\n\n%s', anfrageart, tb),
            })
            _logger.error('ERROR DE ENVIO DIAN\n Factura %s (%s)', self.name, self.id, exc_info=True)
        return True

    def _bring_anfrage_unterzeichnet(self, exe_env, wsdl, art, dok):
        '''
        senden:         1 --> SendBillSync
                        2 --> SendTestSetAsync
        abfrage:        GetStatus
        abfrage_zip:    GetStatusZip
        abfrage_ev:     GetStatusEvent
        '''
        self.ensure_one()
        if art == 'senden':
            if exe_env == '1':
                SendBillAsync_values = self._get_SendBillAsync_values()
                SendBillAsync_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        SendBillAsync_values,
                        'SendBillSync'
                    ),
                    SendBillAsync_values['Id'],
                    self.company_id.certificate_file,
                    self.company_id.certificate_password
                )
                _logger.info('********************** SendBillSync')
            else:
                SendTestSetAsync_values = self._get_SendTestSetAsync_values(
                    dok)
                SendTestSetAsync_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        SendTestSetAsync_values,
                        'SendTestSetAsync'
                    ),
                    SendTestSetAsync_values['Id'],
                    self.company_id.certificate_file,
                    self.company_id.certificate_password
                )
                _logger.info('********************** SendTestSetAsync')
        else:
            if art == 'abfrage':
                GetStatus_values = self._get_GetStatus_values()
                GetStatus_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        GetStatus_values,
                        'GetStatus'
                    ),
                    GetStatus_values['Id'],
                    self.company_id.certificate_file,
                    self.company_id.certificate_password
                )
                _logger.info('********************** GetStatus')

            elif art == 'abfrage_zip':
                GetStatusZip_values = self._get_GetStatusZip_values()
                GetStatusZip_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        GetStatusZip_values,
                        'GetStatusZip'
                    ),
                    GetStatusZip_values['Id'],
                    self.company_id.certificate_file,
                    self.company_id.certificate_password
                )
                _logger.info('********************** GetStatusZip')
            elif art == 'abfrage_ev':
                GetStatus_values = self._get_GetStatus_values()
                GetStatus_values['To'] = wsdl.replace('?wsdl', '')
                signiert_xml = satz.get_xml_soap_with_signature(
                    satz.render_xml_edi(
                        GetStatus_values,
                        'GetStatusEvent'
                    ),
                    GetStatus_values['Id'],
                    self.company_id.certificate_file,
                    self.company_id.certificate_password
                )
                _logger.info('********************** GetStatusEvent')
        signiert_xml = etree.tostring(
            signiert_xml,
            encoding='unicode'
        )
        return signiert_xml

    def _xml_soap_werte_erhalten(self):
        return satz.get_xml_soap_values(
            self.company_id.certificate_file,
            self.company_id.certificate_password
        )

    def _get_SendBillAsync_values(self):
        xml_soap_werte = self._xml_soap_werte_erhalten()
        xml_soap_werte['fileName'] = self.fe_zip_fname.replace('.zip', '')
        xml_soap_werte['contentFile'] = \
            self.fe_zip_file.decode('utf-8', 'ignore')
        return xml_soap_werte

    def _get_SendTestSetAsync_values(self, dok):
        xml_soap_werte = self._get_SendBillAsync_values()
        # TODO: el test set id varia para DS
        xml_soap_werte['testSetId'] = dok == 'sd' and \
            self.company_id.ds_test_set_id or \
            self.company_id.test_set_id
        return xml_soap_werte

    def _get_GetStatusZip_values(self):
        xml_soap_werte = self._xml_soap_werte_erhalten()
        xml_soap_werte['trackId'] = self.fe_zip_key
        return xml_soap_werte

    def _get_GetStatus_values(self):
        xml_soap_werte = self._xml_soap_werte_erhalten()
        uuid = self._context.get('status_uuid', False)
        xml_soap_werte['trackId'] = uuid or self.fe_cufe_cude_ref
        return xml_soap_werte

    def status_erhalten(self):
        # def action_GetStatus(self):
        self.ensure_one()
        wsdl = DIAN['wsdl-hab']
        exe_env, dok = self._zieldok_erhalten()
        if exe_env == '1':
            wsdl = DIAN['wsdl']
        anfrage = self._bring_anfrage_unterzeichnet(
            exe_env, wsdl, 'abfrage', dok)

        antwort = post(
            wsdl,
            headers={
                'content-type': 'application/soap+xml;charset=utf-8'
            },
            data=anfrage
        )
        if antwort.status_code == 200:
            daten_antwort = satz.datenantwort_erhalten(antwort)
            # self._get_status_response(response,send_mail=False)
            self.die_antwort_verarbeiten(
                daten_antwort,
                exe_env=exe_env,
                dok=dok
            )
            self.versandlog_erstellen(
                'GetStatus',
                daten_antwort,
                anfrage,
                exe_env
            )
        else:
            response_text = hasattr(antwort, 'text') \
                and isinstance(antwort.text, str) \
                    and antwort.text.replace('><', '>\n<') or ''
            if satz.is_xml_ok(response_text):
                response_text = satz.xml_to_json(response_text, attrs=False, simple=True)
            raise ValidationError(
                _('Error en metodo GetStatus.'
                  '\nEstado: %s \nReason: %s\n\n%s',
                  antwort.status_code, antwort.reason, response_text))
        return True

    def zip_status_erhalten(self):
        # def action_GetStatusZip(self):
        self.ensure_one()
        wsdl = DIAN['wsdl-hab']
        exe_env, dok = self._zieldok_erhalten()
        if exe_env == '1':
            wsdl = DIAN['wsdl']
        anfrage = self._bring_anfrage_unterzeichnet(
            exe_env, wsdl, 'abfrage_zip', dok)

        antwort = post(
            wsdl,
            headers={
                'content-type': 'application/soap+xml;charset=utf-8'
            },
            data=anfrage
        )
        if antwort.status_code == 200:
            daten_antwort = satz.datenantwort_erhalten(antwort)
            # self._get_status_response(response,send_mail=False)
            self.die_antwort_verarbeiten(
                daten_antwort,
                exe_env=exe_env,
                dok=dok
            )
            self.versandlog_erstellen(
                'GetStatusZip',
                daten_antwort,
                anfrage,
                exe_env
            )
        else:
            response_text = hasattr(antwort, 'text') \
                and isinstance(antwort.text, str) \
                    and antwort.text.replace('><', '>\n<') or ''
            if satz.is_xml_ok(response_text):
                response_text = satz.xml_to_json(response_text, attrs=False, simple=True)
            raise ValidationError(
                _('Error en metodo GetStatusZip. '
                  '\nEstado: %s \nRazón: %s\n\n%s',
                  antwort.status_code, antwort.reason, response_text))
        return True

    def versandlog_erstellen(self, anfrageart,
                             daten_antwort, anfrage, exe_env):
        self.ensure_one()
        name = str(len(self.fe_log_ids) + 1)
        self.env['edi.document.log'].create(
            {
                'name': 'log %s' % name,
                'type_request': anfrageart,
                'move_id': self.id,
                'status_code': daten_antwort.get('status_code', 'ERROR'),
                'reason': daten_antwort.get('reason', 'ERROR'),
                'response': daten_antwort.get(
                    'response_text', 'ERROR').replace('><', '>\n<'),
                'exec_env': exe_env,
                'edi_request_fname': 'Request %s.xml' % name,
                'edi_request_file': b64encode(anfrage.encode())
            }
        )

    def die_antwort_verarbeiten(self, antwort, exe_env, dok):
        '''
            Call the function to process the response
             according to the type of electronic document.
        '''
        if dok == 'ei':
            self.die_antwort_verarbeiten_ei(antwort, exe_env)
        elif dok == 'sd':
            self.die_antwort_verarbeiten_sd(antwort, exe_env)
        else:
            _logger.error(
                _('¡¡¡Respuesta no procesada, el tipo de '
                  'doc electrónico es desconocido.!!!'))

    # def _get_status_response(self, response, send_mail):
    def die_antwort_verarbeiten_ei(self, antwort, exe_env):
        url = ''
        to_return = True
        # status_code = 'other'
        zustand_kod = antwort.get('zustand_kod', 'other')
        zustand_dok = zustand_kod == '00' and 'richtig' \
            or zustand_kod == '99' and 'abgelehnt' \
                or zustand_kod in ('66', '90') and 'fehler' \
                    or not zustand_kod and antwort.get('fehlerliste') and 'abgelehnt' \
                        or False
        zustand_botschaft = antwort.get('zustand_beschreiben', '')
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

        fe_ar_file = antwort.get('xml_base64')
        cufe = antwort.get('xml_dokument_schlussel')
        if cufe:
            url = exe_env == '1' and URL_CUFE['prod'] \
                or URL_CUFE['hab']
            url = url.replace('CUFE', cufe)

        # TODO; validar donde hacer el GetStatus
        if zustand_kod == '0':
            self.status_erhalten()
            return True

        to_write = {
            'fe_state': zustand_kod,
            'fe_response': bild,
            'fe_state_msg': zustand_botschaft
        }
        # TODO
        # VOY AQUI
        # if zustand_dok:
        #     to_write['state'] = zustand_dok
        if fe_ar_file:
            to_write['fe_ar_file'] = fe_ar_file
        if cufe:
            if cufe != self.fe_cufe_cude_ref:
                _logger.warning(
                    _('ERROR!!! El CUFE calculado no es igual'
                      ' al CUFE de la respuesta DIAN'))
        # TODO
        # if url:
        #     to_write['fe_url'] = url
        if fe_ar_file:
            to_write['fe_ad_file'] = self._xml_ad_generieren(fe_ar_file)
        self.write(to_write)
        self.fe_zip_file = b64encode(
            self._get_zipped_file(mit_pdf=True)
        ).decode('utf-8', 'ignore')
        if zustand_kod == '00' and not self.mail_sent and not self.partner_id.dian_not_send_email:
            self.action_send_mail()
        return True

    def _header_steuern_erhalten(self, rate=1, lines={}):
        taxes = {}
        withholding_taxes = {}
        for ln, line in lines.items():
            for tax_code, tax_data in line['TaxesTotal'].items():
                header_group = taxes.setdefault(tax_code, {
                    'name': tax_data['name'],
                    'total': 0,
                    'taxes': {}
                })
                for key, tax in tax_data['taxes'].items():
                    header_tax = header_group['taxes'].setdefault(key, {
                        'base': 0,
                        'amount': 0,
                        'base_unit': 0,
                        'per_unit': tax.get('per_unit')
                    })
                    header_tax['base'] += tax.get('base', 0)
                    header_tax['amount'] += tax.get('amount', 0)
                    header_tax['base_unit'] += tax.get('base_unit', 0)
                    header_group['total'] += tax.get('amount', 0)
            
            for tax_code, tax_data in line['WithTaxesTotal'].items():
                header_group = withholding_taxes.setdefault(tax_code, {
                    'name': tax_data['name'],
                    'total': 0,
                    'taxes': {}
                })
                for key, tax in tax_data['taxes'].items():
                    header_tax = header_group['taxes'].setdefault(key, {
                        'base': 0,
                        'amount': 0,
                        'base_unit': 0,
                        'per_unit': tax.get('per_unit')
                    })
                    header_tax['base'] += tax.get('base', 0)
                    header_tax['amount'] += tax.get('amount', 0)
                    header_tax['base_unit'] += tax.get('base_unit', 0)
                    header_group['total'] += tax.get('amount', 0)

        # ---------------------------------
        # for line in self.line_ids.filtered(lambda ln: ln.tax_line_id
        #         and ln.display_type not in ('line_section', 'line_note')):
        #     tax_id = line.tax_line_id
            
        #     if tax_id.dian_tax_type_id:
        #         tax_code = tax_id.dian_tax_type_id.dian_code
        #         is_withholding = tax_id.dian_tax_type_id.retention
                
        #         if tax_code == 'ZZ':
        #             continue
        #         if tax_id.amount_type in ('percent', 'division'):
        #             if is_withholding and tax_id.amount == 0:
        #                 raise UserError(
        #                     _('El importe de la retención "%s" es igual a '
        #                     'cero (0). La retención debe tener monto '
        #                     'diferente a cero (0).', tax_id.name))
        #             elif is_withholding and tax_id.amount < 0:
        #                 withholding_taxes = line._get_taxes_line_edi(
        #                     withholding_taxes, tax_id,
        #                     rate, 'header', 'fe')
        #             elif is_withholding and tax_id.amount > 0:
        #                 # INFO  Las retenciones se recomienda
        #                 #       no enviarlas a la DIAN.
        #                 #       Solo las positivas que indican una autoretencion.
        #                 pass
        #             # XXX
        #             elif not is_withholding and tax_id.amount < 0:
        #                 raise UserError(
        #                     _('El importe del impuesto "%s" es negativo, '
        #                     'los impuestos deben tener un monto '
        #                     'mayor o igual a cero (0).', tax_id.name))
        #             elif not is_withholding and tax_id.amount > 0:
        #                 taxes = line._get_taxes_line_edi(taxes, tax_id,
        #                                                 rate, 'header', 'fe')
        #         else:
        #             taxes = line._get_taxes_line_edi(taxes, tax_id,
        #                                              rate, 'header', 'fe')
        #     else:
        #         raise UserError(
        #             _('El impuesto "%s", no tiene asignado el código '
        #               'definido por la DIAN.', tax_id.name))

        if '01' not in taxes:
            taxes['01'] = {'total': 0.0,
                           'name': 'IVA',
                           'taxes': {'0.00': {'base': 0,
                                              'amount': 0, }}}
        elif '0.00' not in taxes['01']['taxes']:
            taxes['01']['taxes']['0.00'] = {'base': 0, 'amount': 0, }

        # if '03' not in taxes:
        #     taxes['03'] = {'total': 0.0,
        #                    'name': 'ICA',
        #                    'taxes': {'0.00': {'base': 0.0,
        #                                       'amount': 0.0, }}}
        # if '04' not in taxes:
        #     taxes['04'] = {'total': 0.0,
        #                    'name': 'INC',
        #                    'taxes': {'0.00': {'base': 0,
        #                                       'amount': 0, }}}
        return {
            'TaxesTotal': taxes,
            'WithTaxesTotal': withholding_taxes
        }

    def _get_payment_mean_edi(self):
        self.ensure_one()
        if self.invoice_date < self.invoice_date_due:
            return '2'  # Credito
        elif self.invoice_date == self.invoice_date_due:
            return '1'  # Contado
        else:
            raise ValidationError(
                _('Ocurrió un error!!\n '
                  'La fecha de vencimiento no puede ser menor a la fecha de factura '
                  'o se esta calculando incorrectamente.'))

    # V1.9: trm se trae de balance/amount_currency
    def _get_payment_exchange_rate(self, tdoc='fe'):
        company_currency = self.company_id.currency_id
        out = {}
        if self.currency_id.id != company_currency.id:
            rate = 1
            date = self.date or fields.Date.context_today(self)
            lines = self.invoice_line_ids.filtered(lambda ln:
                        ln.display_type not in ('line_section', 'line_note') \
                            and ln.balance != 0 and ln.amount_currency != 0)
            if lines:
                rate = abs(sum([line.balance/line.amount_currency for line in lines])/len(lines))
            else:
                rate = 1/self.invoice_currency_rate
            rate = round(rate, 2)
            if tdoc == 'ds':
                out = {
                    'SourceCurrencyCode': self.currency_id.name,
                    'TargetCurrencyCode': company_currency.name,
                    'CalculationRate': rate,
                    'Date': date
                }
            else:
                out = {
                    'SourceCurrencyCode': company_currency.name or 'COP',
                    'SourceCurrencyBaseRate': rate,
                    'TargetCurrencyCode': self.currency_id.name,
                    'CalculationRate': 1/rate,
                    'Date': date
                }
        return out

    def _ist_mandat(self):
        '''
            Determina si el documento corresponde a una operación de mandato
            (tipo de operación 11), sea propia o heredada de la factura
            referencia.

            No basta con mirar operation_type_ei_ref: ese campo lo escribe
            _get_billing_reference(), que corre despues de
            _linienwerte_erhalten(), asi que en el primer calculo del XML de
            una nota todavia esta vacio.
        '''
        self.ensure_one()
        if self.fe_operation_type == '11' \
                or self.operation_type_ei_ref == '11':
            return True
        inv_ref_id = False
        if self.type_note == 'credit':
            inv_ref_id = self.reversed_entry_id
        elif self.type_note == 'debit':
            inv_ref_id = self.debit_origin_id
        return bool(inv_ref_id) and inv_ref_id.fe_operation_type == '11'

    def _linienwerte_erhalten(self, trm=1):
        invoice_lines = {}
        count = 1
        ist_mandat = self._ist_mandat()
        for invoice_line in self.invoice_line_ids.filtered(
                lambda ln: ln.display_type == 'product'):
            currency_id = invoice_line.currency_id
            price_unit = invoice_line.price_unit
            quantity = invoice_line.quantity
            discount = invoice_line.discount
            total_without_disc = price_unit * quantity
            disc_amount = total_without_disc * (discount / 100)
            subtotal = invoice_line.price_subtotal 
            # subtotal = total_without_disc - disc_amount
            total_without_disc = currency_id.round(total_without_disc) * trm
            disc_amount = currency_id.round(disc_amount) * trm
            subtotal = currency_id.round(subtotal) * trm
            price_unit = price_unit * trm
            # if price_unit == 0 or quantity == 0:
            #     raise ValidationError(
            #         _('Líneas de factura con precio o cantidad cero (0) '
            #           'generan rechazo en la facturación electrónica.'))
            error_msg = ''
            if not invoice_line.product_uom_id.dian_uom_id:
                error_msg += _('- La unidad de medida "%s", no tiene el '
                               'código definido por la DIAN.\n',
                               invoice_line.product_uom_id.name)
            if abs(discount) > 100:
                error_msg += _('- El descuento o cargo en las líneas de la '
                               'factura no puede superar el 100%.\n')
            if abs(disc_amount) > total_without_disc:
                error_msg += _('- El descuento o cargo supera el valor base '
                               'en la linea del producto %s\n',
                               invoice_line.name)
            if total_without_disc < 0:
                error_msg += _('- El valor base en la linea del producto %s '
                               'no debe ser negativo. (%s)\n',
                               invoice_line.name, total_without_disc)
            if not invoice_line.product_id \
                    or not invoice_line.product_id.default_code:
                error_msg += _('- La línea de factura %s no tiene referencia '
                               'en el producto.\n', invoice_line.name)
            InformationContentProviderParty = False
            if ist_mandat:
                if not invoice_line.fe_mandante_id:
                    error_msg += _('- La línea de factura %s no tiene '
                                   'Mandante (requerido para el tipo de '
                                   'operación 11).\n', invoice_line.name)
                else:
                    error11, InformationContentProviderParty = \
                        invoice_line.fe_mandante_id._get_TaxRepresentativeParty()
                    if error11:
                        error_msg += error11
            if error_msg:
                raise ValidationError(
                    _('Se identificaron los siguientes errores a nivel de línea en la'
                      ' factura id=%s:\n\n%s', self.id, error_msg))
            disc_charge = []
            if discount != 0:
                disc_charge.append({
                    'ID': 1,
                    'type': discount < 0 and 'true' or 'false',
                    'reason': discount < 0 and 'Cargo por línea' or 'Descuento por línea',
                    'percent': '{:.2f}'.format(abs(discount)),
                    'amount': '{:.3f}'.format(abs(disc_amount)),
                    'base': '{:.3f}'.format(total_without_disc),
                })

            invoice_lines[count] = {}
            # TODO v1.9: Falta definir nota para AIU
            invoice_lines[count]['Note'] = satz.escape_xml(invoice_line.name or '')
            invoice_lines[count]['unitCode'] = invoice_line.product_uom_id \
                and invoice_line.product_uom_id.dian_uom_id \
                    and invoice_line.product_uom_id.dian_uom_id.dian_code or ''
            invoice_lines[count]['Quantity'] = '{:.2f}'.format(
                invoice_line.quantity)
            invoice_lines[count]['LineExtensionAmount'] = '{:.2f}'.format(
                subtotal) # invoice_line.price_subtotal)
            # TODO v1.9: Agregar precio de referencia cuando es un obsequio o muestra comercial
            # invoice_lines[count]['PricingReference'] = ...
            invoice_lines[count]['AllowanceCharge'] = disc_charge
            invoice_lines[count]['TaxesTotal'] = {}
            invoice_lines[count]['WithTaxesTotal'] = {}
            invoice_lines[count]['ItemDescription'] = satz.escape_xml(invoice_line.name[:290] or '')
            invoice_lines[count]['BrandName'] = satz.escape_xml(invoice_line.product_id \
                and invoice_line.product_id.dian_brand or '')
            invoice_lines[count]['ModelName'] = satz.escape_xml(invoice_line.product_id \
                and invoice_line.product_id.dian_model or '')
            invoice_lines[count]['SellersItemIdentification'] = \
                satz.escape_xml(invoice_line.product_id.default_code)
            invoice_lines[count]['StandardItemIdentification'] = \
                satz.escape_xml(invoice_line._get_product_standard_code())
            invoice_lines[count]['AdditionalItemProperty'] =  invoice_line._zeilenattribute_abrufen()
            invoice_lines[count]['IDschemeID'] = invoice_line._scheme_id_abrufen()
            invoice_lines[count]['InformationContentProviderParty'] = InformationContentProviderParty
            invoice_lines[count]['PriceAmount'] = '{:.4f}'.format(price_unit)

            for tax in invoice_line.tax_ids:  # tax_line_id: # tax_ids
                if tax.amount_type == 'group':
                    tax_ids = tax.children_tax_ids
                else:
                    tax_ids = tax

                for tax_id in tax_ids:
                    if tax_id.dian_tax_type_id:
                        if tax_id.dian_tax_type_id.dian_code == 'ZZ':
                            continue
                        is_withholding = tax_id.dian_tax_type_id.retention
                        if tax_id.amount_type in ('percent', 'division'):
                            if is_withholding and tax_id.amount == 0:
                                raise UserError(
                                    _('El importe de la retención "%s" es igual '
                                    'a cero (0). La retención debe tener '
                                    'monto diferente a cero (0).', tax_id.name))
                            elif is_withholding and tax_id.amount < 0:
                                invoice_lines[count]['WithTaxesTotal'] = \
                                    invoice_line._get_taxes_line_edi(
                                        invoice_lines[count]['WithTaxesTotal'],
                                        tax_id,
                                        trm,
                                        'item',
                                        'fe'
                                )
                            elif is_withholding and tax_id.amount > 0:
                                pass
                            elif not is_withholding and tax_id.amount < 0:
                                raise UserError(
                                    _('El importe del impuesto "%s" es negativo, '
                                    'el impuesto debe tener un monto '
                                    'mayor o igual a cero (0).', tax_id.name))
                            # TODO: validar si se agrega para generar datos del impuesto
                            elif not is_withholding and tax_id.amount == 0:
                                pass
                            else:
                                invoice_lines[count]['TaxesTotal'] = \
                                    invoice_line._get_taxes_line_edi(
                                        invoice_lines[count]['TaxesTotal'],
                                        tax_id,
                                        trm,
                                        'item',
                                        'fe'
                                )
                        else:
                            # TODO: logica impuestos tasa nominal
                            if tax_id.dian_tax_type_id.dian_code == '34' and not invoice_line.product_id.dian_nominal_tax:
                                raise ValidationError(
                                    _('Se debe configurar "Volumen en mililitros" en el producto: %s cuando se aplican impuestos IBUA.', invoice_line.product_id.display_name)
                                )
                            invoice_lines[count]['TaxesTotal'] = \
                                    invoice_line._get_taxes_line_edi(
                                        invoice_lines[count]['TaxesTotal'],
                                        tax_id,
                                        trm,
                                        'item',
                                        'fe'
                                )
                    else:
                        raise UserError(
                            _('El impuesto "%s", no tiene asignado el código'
                              ' definido por la DIAN..', tax.name))

            if '01' not in invoice_lines[count]['TaxesTotal']:
                invoice_lines[count]['TaxesTotal']['01'] = {
                    'total': 0.0,
                    'name': 'IVA',
                    'taxes': {'0.00': {'base': (invoice_line.price_subtotal or (invoice_line.price_unit * invoice_line.quantity)) * trm,
                                       'amount': 0.0}}
                }
            # if '03' not in invoice_lines[count]['TaxesTotal']:
            #     invoice_lines[count]['TaxesTotal']['03'] = {
            #         'total': 0.0,
            #         'name': 'ICA',
            #         'taxes': {'0.00': {'base': invoice_line.price_subtotal,
            #                            'amount': 0.0}}
            #     }
            # if '04' not in invoice_lines[count]['TaxesTotal']:
            #     invoice_lines[count]['TaxesTotal']['04'] = {
            #         'total': 0.0,
            #         'name': 'INC',
            #         'taxes': {'0.00': {'base': invoice_line.price_subtotal,
            #                            'amount': 0.0}}
            #     }
            invoice_lines[count]['TaxesTotal'] = dict(sorted(invoice_lines[count]['TaxesTotal'].items()))
            count += 1
        return invoice_lines

    def _get_zipped_file(self, mit_pdf=False):
        '''
            Create a zip file with the attached
            document file or xml file and pdf file.
        '''
        self.ensure_one()
        files_to_zip = []

        if self.fe_ad_file:
            files_to_zip.append((self.fe_ad_fname, self.fe_ad_file))
        else:
            files_to_zip.append((self.fe_xml_fname, self.fe_xml_file))
        if mit_pdf:
            if not self.fe_pdf_file:
                self.fe_pdf_file = self._pdf_datei_bekommen()
            files_to_zip.append((self.fe_pdf_fname, self.fe_pdf_file))
        file_zip = satz.get_zipped_file(files_to_zip)
        return file_zip

    def action_zip_create(self):
        self.ensure_one()
        self.fe_zip_file = b64encode(
            self._get_zipped_file(mit_pdf=True)
        ).decode('utf-8', 'ignore')

    def _get_billing_reference(self):
        billing_reference = {}
        inv_ref_id = False
        if self.type_note == 'credit':
            inv_ref_id = self.reversed_entry_id
        elif self.type_note == 'debit':
            inv_ref_id = self.debit_origin_id

        if not inv_ref_id:
            raise ValidationError(
                _('No es posible identificar la factura '
                  'referencia de esta Nota.'))

        if inv_ref_id.state == 'posted':
            if inv_ref_id.fe_state == '00' or inv_ref_id.fe_send_later:
                billing_reference = {
                    'ID': inv_ref_id.name,
                    'UUID': inv_ref_id.fe_cufe_cude_ref,
                    'IssueDate': inv_ref_id.invoice_date,
                    'CustomizationID': inv_ref_id.fe_operation_type
                }
                self.write({
                    'name_ei_ref': inv_ref_id.name,
                    'uuid_ei_ref': inv_ref_id.fe_cufe_cude_ref,
                    'issue_date_ei_ref': inv_ref_id.invoice_date,
                    'operation_type_ei_ref': inv_ref_id.fe_operation_type
                })
            else:
                raise ValidationError(
                    _('El documento electrónico de la factura referencia (%s)'
                      ' no está procesado correctamente por la DIAN. \n\n'
                      'Valide que la factura no se encuentre rechazada '
                      'o sin procesar ante la DIAN', inv_ref_id.name))
        else:
            raise ValidationError(
                _('Para publicar esta nota se requiere que la '
                  'factura referencia (%s) esté publicada.',
                  inv_ref_id.name))
        if not billing_reference:
            raise UserError(
                _('La nota %s no tiene referencia de facturación \n\n',
                  _('crédito') if self.type_note == 'credit'
                  else _('débito') if self.type_note == 'debit'
                  else ''))
        return billing_reference

    # XXX Not use
    def send_failure_email(self):
        subject = _(
            'ALERTA! La Factura %s no fue enviada a la DIAN.', self.name)
        msg_body = _('''
            Cordial Saludo,<br/><br/>La factura {inv}
             del cliente {cli} no pudo ser
             enviada a la Dian según el protocolo establecido previamente. Por
             favor revise el estado de la misma en el menú Documentos Dian e
             intente reprocesarla según el procedimiento definido.
            <br/> {com}.''').format(inv=self.name,
                                    cli=self.partner_id.name,
                                    com=self.company_id.name)
        email_to = self.company_id.edi_email_error

        # if email_ids:
        #     email_to = ''

        # for mail_id in email_ids:
        #     email_to += mail_id.email.strip() + ','
        if not email_to:
            raise UserError(
                _('El(los) correo(s) para fallas de facturas electrónicas '
                  'no está configurado. \nNo se le notificará '
                  'si algo sale mal. \n '
                  'Vaya a Configuración > Compañía > Correos para '
                  'notificación de errores.'))
        mail_obj = self.env['mail.mail']
        msg_vals = {
            'subject': subject,
            'email_to': email_to,
            'body_html': msg_body}
        msg_id = mail_obj.create(msg_vals)
        msg_id.send()

        return True

    # TODO: Validar qué debe ir en el adjunto
    def action_send_mail(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_co_bloodo.type_send_ei_mail', 'once_cc')
        msg = _('Su factura no ha sido validada.')
        attach_obj = self.env['ir.attachment']
        if not self.name:
            raise UserError(msg)
        template_id = self.env.ref('l10n_co_bloodo.dian_email_template')
        attach_ids = attach_obj
        if self.fe_zip_file:
            zip_id = attach_obj.search([
                ('name', '=', self.fe_zip_fname),
                ('res_model', '=', 'account.move'),
                ('res_id', '=', self.id),
                ('res_field', '=', False)
            ])
            if zip_id:
                zip_id.datas = self.fe_zip_file
            else:
                zip_id = attach_obj.create({
                    'name': self.fe_zip_fname,
                    'res_model': 'account.move',
                    'res_id': self.id,
                    'type': 'binary',
                    'datas': self.fe_zip_file,
                })
            attach_ids |= zip_id
        if self.company_id.email_attach_doc:
            attach_ids |= attach_obj.search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', self.id),
                ('res_field', '=', False)
            ])
        if param == 'once_cc':
            email_to_vals = template_id._render_field('email_to', self.ids)[self.id]
            email_to = tools.email_split(email_to_vals)
            partner_obj = self.env['res.partner']
            partner_ids = []
            for mail in email_to:
                partner = partner_obj.sudo().find_or_create(mail)
                partner_ids.append(partner.id)
            email_vals = {
                'is_notification': True,
            }
            if partner_ids:
                email_vals['email_to'] = False
                email_vals['recipient_ids'] = [Command.link(pid) for pid in partner_ids]
            if attach_ids:
                email_vals['attachment_ids'] = [(4, tt, 0) for tt in attach_ids.ids]
            force_send = self._context.get('eimail_force', False)
            template_id.send_mail(self.id, force_send=force_send, email_values=email_vals,
                                  email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature')
        else:
            if attach_ids:
                template_id.attachment_ids = [(4, tt, 0) for tt in attach_ids.ids]
            kwargs = {
                'notify': False
            }
            self.with_context(no_new_invoice=True).message_post_with_template(
                template_id.id,
                email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
                **kwargs)
            if attach_ids:
                template_id.attachment_ids = [(3, z, 0) for z in attach_ids.ids]
        self.write({'mail_sent': True})
        return True

    def _pdf_datei_bekommen(self):
        '''
            Return base64 pdf file for e-document
        '''
        report_obj = self.env['ir.actions.report']
        report_id = self._get_einvoice_report()
        if report_id:
            report_name = report_id.report_name
        else:
            report_name = 'l10n_co_bloodo.action_report_einvoicing_print'

        pdf = report_obj._render_qweb_pdf(report_name, [self.id])
        return b64encode(pdf[0])

    def _daten_fur_ad_erhalten(self, ar_file=False):
        self.ensure_one()
        cac = '{urn:oasis:names:specification:ubl:' \
            'schema:xsd:CommonAggregateComponents-2}'
        cbc = '{urn:oasis:names:specification:ubl:' \
            'schema:xsd:CommonBasicComponents-2}'
        werte = {}
        xml_file = b64decode(self.fe_xml_file)
        # .decode('utf-8', 'ignore')
        ar_file = b64decode(
            ar_file and ar_file.encode('utf-8') or
            self.fe_ar_file)
        # .decode('utf-8', 'ignore')
        # parser = etree.XMLParser(remove_blank_text=False, remove_comments=False)
        werte = {
            'xml_file': xml_file.decode('utf-8'),
            'ApplicationResponse': ar_file.decode('utf-8'),
            'type_doc': self._get_type_document(),
        }
        xml_file = etree.fromstring(xml_file)
        ar_file = etree.fromstring(ar_file)
        # Consecutivo de la factura aunque puede ser generado por uno
        werte['ID'] = xml_file.findall('%sID' % cbc)[0].text
        # Cufe/Cude
        werte['UUID'] = xml_file.findall('%sUUID' % cbc)[0].text
        # Codigo de resultado de la validación
        response_code = ar_file.findall(
            '{cac}DocumentResponse/{cac}Response/{cbc}ResponseCode'.format(
                cac=cac,
                cbc=cbc
            )
        )
        werte['ValidationResultCode'] = response_code and \
            response_code[0].text or ''
        # Fecha de la validación
        werte['ValidationDate'] = ar_file.findall('%sIssueDate' % cbc)[0].text
        # Hora de la validación
        werte['ValidationTime'] = ar_file.findall('%sIssueTime' % cbc)[0].text
        # ambiente pruebas o prod
        werte['ProfileExecutionID'] = xml_file.findall(
            '%sProfileExecutionID' % cbc)[0].text
        for element in xml_file.findall(
                '{cac}AccountingSupplierParty/{cac}Party/'
                '{cac}PartyTaxScheme'.format(
                    cac=cac,
                    cbc=cbc
                )):
            RegistrationName = element.findall('%sRegistrationName' % cbc)[0]
            CompanyID = element.findall('%sCompanyID' % cbc)[0]
            TaxLevelCode = element.findall('%sTaxLevelCode' % cbc)[0]
            TaxScheme = element.findall('%sTaxScheme' % cac)[0]
            werte['SenderParty'] = satz.escape_xml({
                'RegistrationName': RegistrationName.text,
                'CompanyID': CompanyID.text,
                'schemeID': CompanyID.get('schemeID'),
                'schemeName': CompanyID.get('schemeName'),
                'TaxLevelCode': TaxLevelCode.text,
                'TaxSchemeID': TaxScheme[0].text,
                'TaxSchemeName': TaxScheme[1].text
            })
        for element in xml_file.findall(
            '{cac}AccountingCustomerParty/{cac}'
                'Party/{cac}PartyTaxScheme'.format(cac=cac, cbc=cbc)):
            RegistrationName = element.findall('%sRegistrationName' % cbc)[0]
            CompanyID = element.findall('%sCompanyID' % cbc)[0]
            TaxLevelCode = element.findall('%sTaxLevelCode' % cbc)[0]
            TaxScheme = element.findall('%sTaxScheme' % cac)[0]
            werte['ReceiverParty'] = satz.escape_xml({
                'RegistrationName': RegistrationName.text,
                'CompanyID': CompanyID.text,
                'schemeID': CompanyID.get('schemeID'),
                'schemeName': CompanyID.get('schemeName'),
                'TaxLevelCode': TaxLevelCode.text,
                'TaxSchemeID': TaxScheme[0].text,
                'TaxSchemeName': TaxScheme[1].text
            })
        time_now = fields.Datetime.context_timestamp(self,
                                                     fields.Datetime.now())
        werte['IssueDate'] = time_now.strftime('%Y-%m-%d')
        werte['IssueTime'] = time_now.strftime('%H:%M:%S-05:00')
        return werte

    def create_attachedDocument(self):
        self.ensure_one()
        if not self.fe_ar_file:
            raise ValidationError(_('Esta factura no tiene '
                                    'un ApplicationResponse'))
        if not self.fe_xml_file:
            raise ValidationError(_('Esta factura no tiene '
                                    'un archivo de factura XML'))
        self.fe_ad_file = self._xml_ad_generieren()

    def _xml_ad_generieren(self, ar_file=False):
        '''
            Return base64 from AttachedDocument file generated
        '''
        self.ensure_one()
        xml_file = satz.render_xml_edi(
            self._daten_fur_ad_erhalten(ar_file),
            'attachment'
        )
        xml_sign = satz.xml_mit_signatur_erhalten(
            xml_file,
            self.company_id.signature_policy_url,
            self.company_id.signature_policy_description,
            self.company_id.signature_policy_file,
            self.company_id.certificate_file,
            self.company_id.certificate_password
        )
        parser = etree.XMLParser(remove_blank_text=False, remove_comments=True)
        xml_sign = etree.fromstring(xml_sign, parser=parser)
        ns = xml_sign.nsmap
        ns['inv'] = ns.pop(None)
        attach_element = xml_sign.xpath(
            '//cac:Attachment/cac:ExternalReference/cbc:Description',
            namespaces=ns)
        for element in attach_element:
            element.text = etree.CDATA(element.text)
        xml_sign = etree.tostring(xml_sign, encoding='UTF-8')
        xml_sign = xml_sign.decode().replace(
            '<ext:ExtensionContent/>', '')
        return b64encode(xml_sign.encode()).decode('utf-8', 'ignore')

    def action_reverse(self):
        res = super(AccountMove, self).action_reverse()
        ctx = eval(res.get('context', '{}'))
        if self.is_einvoicing_journal:
            ctx['default_is_edoc'] = True
            res['context'] = str(ctx)
        return res

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if not default_values_list:
            default_values_list = [{} for move in self]
        for move, default_values in zip(self, default_values_list):
            if move.move_type == 'out_invoice':
                default_values.update({
                    'type_note': 'credit',
                })
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    def _get_ubl_namespaces(self, tree):
        ''' If the namespace is declared with xmlns='...',
         the namespaces map contains the 'None' key that causes an
        TypeError: empty namespace prefix is not supported in XPath
        Then, we need to remap arbitrarily this key.

        :param tree: An instance of etree.
        :return: The namespaces map without 'None' key.
        '''
        namespaces = tree.nsmap
        namespaces['inv'] = namespaces.pop(None)
        return namespaces

    def decode_xml_ubl_2_1(self, tree):
        """ Decodes an UBL invoice into an invoice.

        :param tree:    the UBL tree to decode.
        :param invoice: the invoice to update or an empty recordset.
        :returns:       the invoice where the UBL data was imported.
        """

        namespaces = self._get_ubl_namespaces(tree)

        def _find_value(xpath, element=tree):
            return self._find_value(xpath, element, namespaces)

        def _find_element(xpath, element=tree, all=False):
            return self._find_element(xpath, element, namespaces, all)

        root_name = tree.tag.replace('{%s}' % namespaces['inv'], '')
        invoice_vals = {}
        invoice_vals['CustomizationID'] = _find_value('//cbc:CustomizationID')
        invoice_vals['ProfileID'] = _find_value('//cbc:ProfileID')
        invoice_vals['ProfileExecutionID'] = _find_value(
            '//cbc:ProfileExecutionID')
        invoice_vals['ID'] = _find_value('//cbc:ID')
        # UUID
        elements = tree.xpath('//cbc:UUID', namespaces=namespaces)
        invoice_vals['UUID'] = elements and elements[0].text or None
        invoice_vals['UUID_schemeName'] = elements and \
            elements[0].attrib.get('schemeName') or False
        invoice_vals['IssueDate'] = _find_value('//cbc:IssueDate')
        invoice_vals['IssueTime'] = _find_value('//cbc:IssueTime')
        invoice_vals['InvoiceTypeCode'] = _find_value(f'//cbc:{root_name}TypeCode')
        # Note
        elements = tree.xpath('cbc:Note', namespaces=namespaces)
        invoice_vals['Note'] = elements and [
            element.text for element in elements] or False
        invoice_vals['DocumentCurrencyCode'] = _find_value(
            '//cbc:DocumentCurrencyCode')
        invoice_vals['LineCountNumeric'] = _find_value(
            '//cbc:LineCountNumeric')
        invoice_vals['InstructionID'] = _find_value('//cbc:InstructionID')
        invoice_vals['PaymentDueDate'] = _find_value('//cbc:PaymentDueDate')
        invoice_vals['LossRiskResponsibilityCode'] = _find_value(
            '//cbc:LossRiskResponsibilityCode')
        invoice_vals['AccountingSupplierParty'] = self._partnerparty_erhalten(
            tree, 'Supplier') or {}
        invoice_vals['AccountingCustomerParty'] = self._partnerparty_erhalten(
            tree, 'Customer') or {}

        # Lines
        lines_elements = _find_element(f'//cac:{root_name}Line', all=True)
        invoice_vals['InvoiceLine'] = []
        for eline in lines_elements:
            doc_qty = (root_name == 'CreditNote' and 'Credited') \
                or (root_name == 'DebitNote' and 'Debited') \
                or 'Invoiced'
            line = {
                'SellersItemIdentification': _find_value(
                    'cac:Item/cac:SellersItemIdentification/cbc:ID',
                    eline
                ),
                'Note': [
                    n.text for n in _find_element('cbc:Note', eline, all=True)
                ],
                'StandardItemIdentification': [
                    {
                        'ID': s.text,
                        'schemeID': s.attrib.get('schemeID', None)
                    } for s in _find_element(
                        'cac:Item/cac:StandardItemIdentification/cbc:ID',
                        eline,
                        all=True
                    )
                ],
                'InvoicedQuantity': float(_find_value(
                    f'cbc:{doc_qty}Quantity', eline)) or 1.0,
                'PriceAmount': float(_find_value(
                    'cac:Price/cbc:PriceAmount', eline)) or 0.0,
                'LineExtensionAmount': float(_find_value(
                    'cbc:LineExtensionAmount', eline)) or 0.0,
                'Description': _find_value(
                    'cac:Item/cbc:Description', eline),
                'TaxTotal': [],
                'AllowanceCharge': []
            }
            echarges = _find_element(
                'cac:AllowanceCharge', element=eline, all=True)
            for echarge in echarges:
                charge = {
                    'ID': _find_value('cbc:ID', element=echarge),
                    'ChargeIndicator': _find_value(
                        'cbc:ChargeIndicator', element=echarge),
                    'AllowanceChargeReason': _find_value(
                        'cbc:AllowanceChargeReason', element=echarge),
                    'MultiplierFactorNumeric': _find_value(
                        'cbc:MultiplierFactorNumeric', element=echarge),
                    'Amount': _find_value('cbc:Amount', element=echarge),
                    'BaseAmount': _find_value(
                        'cbc:BaseAmount', element=echarge)
                }
                line['AllowanceCharge'].append(charge)
            etaxes = _find_element(
                'cac:TaxTotal/cac:TaxSubtotal', element=eline, all=True)
            for etax in etaxes:
                tax = {
                    'Percent': _find_value(
                        'cac:TaxCategory//cbc:Percent', element=etax),
                    'ID': _find_value(
                        'cac:TaxCategory//cbc:ID', element=etax)
                }
                line['TaxTotal'].append(tax)
            invoice_vals['InvoiceLine'].append(line)
        return invoice_vals

    ##############################################################

    def lieferant_rechnung_einfuhren(self):
        if self.state == 'cancel':
            raise ValidationError(
                _('Esta operación no está permitida '
                  'si el documento está cancelado.'))
        ctx = {
            'default_move_id': self.id,
            'default_msg': _(
                'Por favor, Cargue el archivo que desea subir '
                'como factura de proveedor.\n'
                'Puede ser el documento XML <AttachedDocument> '
                'o <Invoice> o el archivo .Zip que los contiene.'
            ),
            'default_btn_create': False,
            'default_add_header': True
        }
        if self.state == 'posted':
            ctx['default_add_header'] = False
            ctx['default_add_lines'] = False
        return {
            'name': _('Import supplier e-invoice'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'invoice.import.wizard',
            'target': 'new',
            'context': ctx
        }

    def decode_ei_xml_file(self, xml_ei=False):
        '''
            input: xml file in base64.
            out: {}
        '''
        self.ensure_one()
        if not xml_ei:
            raise ValidationError(
                _('No hay un archivo XML para procesar.'))
        xml_file = b64decode(xml_ei)
        parser = etree.XMLParser(remove_blank_text=True, remove_comments=True)
        xml_tree = etree.fromstring(xml_file, parser=parser)
        namespaces = self._get_ubl_namespaces(xml_tree)
        root_name = xml_tree.tag.replace('{%s}' % namespaces['inv'], '')
        if root_name == 'AttachedDocument':  # in xml_tree.tag:
            elements = xml_tree.xpath(
                '//cac:Attachment/cac:ExternalReference/cbc:Description',
                namespaces=namespaces
            )
            if elements:
                xml_inv = elements[0].text
                xml_inv = etree.fromstring(xml_inv.encode(), parser=parser)
        elif root_name in ('Invoice', 'CreditNote', 'DebitNote'):
            xml_inv = xml_tree
        else:
            raise ValidationError(
                _('XML desconocido\n\n'
                  'XML no corresponde a una factura electrónica.'))
        xml_data = self.decode_xml_ubl_2_1(xml_inv)
        return xml_data

    def _find_value(self, xpath, xml_element, namespaces=None):
        element = xml_element.xpath(xpath, namespaces=namespaces)
        return element[0].text if element else None

    def _find_element(self, xpath, xml_element, namespaces=None, all=False):
        element = xml_element.xpath(xpath, namespaces=namespaces)
        if element:
            return all and element or element[0]
        else:
            if all:
                return []
            else:
                return None

    def _retrieve_product(self, name=None, default_code=None, barcode=None):
        '''
        Search all products and find one that matches one of the parameters.

        :param name:            The name of the product.
        :param default_code:    The default_code of the product.
        :param barcode:         The barcode of the product.
        :returns:               A product or an empty recordset if not found.
        '''
        domains = []
        for value, domain in (
            (name, ('name', 'ilike', name)),
            (default_code, ('default_code', '=', default_code)),
            (barcode, ('barcode', '=', barcode)),
        ):
            if value is not None:
                domains.append([domain])

        domain = Domain.OR(domains)
        return self.env['product.product'].search(domain, limit=1)

    def _retrieve_tax(self, amount, type_tax_use):
        '''Search all taxes and find one that matches all of the parameters.

        :param amount:          The amount of the tax.
        :param type_tax_use:    The type of the tax.
        :returns:               A tax or an empty recordset if not found.
        '''
        domains = [
            [('amount', '=', float(amount))],
            [('type_tax_use', '=', type_tax_use)]
        ]

        return self.env['account.tax'].search(
            Domain.AND(domains),
            order='sequence ASC',
            limit=1
        )

    def _partner_abrufen(self, vat, doc_type):
        doc_type_id = self.env['l10n_latam.identification.type'].search(
            [('dian_code', '=', doc_type)],
            limit=1
        )
        if not doc_type_id:
            raise ValidationError(
                _('El XML no tiene un tipo de identificación'
                  ' reconocido por esta base de datos [%s]', doc_type))

        normalized_vat = vat.replace(' ', '')
        partner_id = self.env['res.partner'].search(
            [('vat', 'in', (normalized_vat, vat)),
             ('l10n_latam_identification_type_id', '=', doc_type_id.id)],
            limit=1
        )
        if not partner_id:
            return False
            # raise ValidationError(_(
            #     'The contact identified with %s %s cannot'
            #     ' be found in this database.'
            # ) % (doc_type_id.name, vat))
        return partner_id

    def _partnerparty_erhalten(self, tree, type_partner):
        namespaces = self._get_ubl_namespaces(tree)

        def _find_value(xpath, element=tree):
            return self._find_value(xpath, element, namespaces)

        def _find_element(xpath, element=tree, all=False):
            return self._find_element(xpath, element, namespaces, all)
        if tree is None:
            raise ValidationError(
                _('No hay un elemento tree para obtener los datos del tercero.'))
        r = '//cac:Accounting%sParty' % type_partner
        out = {}
        out['AdditionalAccountID'] = _find_value(
            f'{r}//cbc:AdditionalAccountID')
        out['Name'] = _find_value(f'{r}//cac:Party/cac:PartyName/cbc:Name')
        out['CityCode'] = _find_value(
            f'{r}//cac:PhysicalLocation/cac:Address/cbc:ID')
        out['CityName'] = _find_value(
            f'{r}//cac:PhysicalLocation/cac:Address/cbc:CityName')
        out['PostalZone'] = _find_value(
            f'{r}//cac:PhysicalLocation/cac:Address/cbc:PostalZone')
        out['CountrySubentity'] = _find_value(
            f'{r}//cac:PhysicalLocation/cac:Address/cbc:CountrySubentity')
        out['CountrySubentityCode'] = _find_value(
            f'{r}//cac:PhysicalLocation/cac:Address/cbc:CountrySubentityCode')
        out['AddressLine'] = _find_value(
            f'{r}//cac:PhysicalLocation/cac:Address/cac:AddressLine/cbc:Line')
        out['CountryCode'] = _find_value(
            f'{r}//cac:PhysicalLocation/cac:Address/cac:Country'
            '/cbc:IdentificationCode')
        out['CountryName'] = _find_value(
            f'{r}//cac:PhysicalLocation/cac:Address/cac:Country/cbc:Name')
        id_partner = _find_element(f'{r}//cac:PartyTaxScheme/cbc:CompanyID')
        out['CompanyID'] = id_partner.text
        out['schemeID'] = id_partner.attrib.get('schemeID', None)
        out['schemeName'] = id_partner.attrib.get('schemeName', None)
        tax_level_code = _find_element(
            f'{r}//cac:PartyTaxScheme/cbc:TaxLevelCode')
        out['TaxLevelCode'] = tax_level_code is not None \
            and tax_level_code.text or None
        out['listName'] = tax_level_code is not None \
            and tax_level_code.attrib.get('listName', None) or None
        out['TaxSchemeID'] = _find_value(
            f'{r}//cac:PartyTaxScheme/cac:TaxScheme/cbc:ID')
        out['TaxSchemeName'] = _find_value(
            f'{r}//cac:PartyTaxScheme/cac:TaxScheme/cbc:Name')
        # Contact
        out['Telephone'] = _find_value(
            f'{r}//cac:Party/cac:Contact/cbc:Telephone')
        out['ElectronicMail'] = _find_value(
            f'{r}//cac:Party/cac:Contact/cbc:ElectronicMail')
        return out

    # Event
    def _ereignis_senden(self, ev_code):
        '''
        Generate the xml of the event,
        send it to the DIAN and
        record the response to the invoice.
        input: event code
        '''
        exe_env = self.company_id.target_environment_id
        ereigniswerte = self._daten_fur_ereignis_abrufen(ev_code)
        xml_str = self._ereignis_xml_fullen(ereigniswerte)
        antwort = self.ereignis_senden_anfrage(xml_str)
        if antwort.get('zustand_kod') == '00':
            uuid = self.fe_cufe_cude_ref
            if self.move_type in ('in_invoice', 'in_refund'):
                uuid = self.uuid_ei_ref
            if not uuid:
                raise ValidationError(
                    _('No hay un CUFE de referencia para consultar estado.'))
            self = self.with_context(status_uuid=uuid)
            antwort = self.ereignis_status_erhalten(exe_env)
        out = self.die_ereignisantwort_verarbeiten(
            antwort, xml_str, exe_env, ev_code)
        return out

    def empfangsbestatigung(self):
        '''
        Acknowledgment of receipt
        '''
        _logger.info('Acuse de Recibo')
        out = self._ereignis_senden('030')
        return out

    def produktbeleg(self):
        '''
        Product receipt
        '''
        _logger.info('Recibo del producto')
        out = self._ereignis_senden('032')
        return out

    def ausdruckliche_ahnname(self):
        '''
        Express acceptance
        '''
        _logger.info('Aceptación expresa')
        out = self._ereignis_senden('033')
        return out

    def stillschweigende_ahnname(self):
        '''
        Tacit acceptance
        '''
        _logger.info('Aceptación tácita')
        self.ensure_one()
        days_after_032 = self._get_business_days(
            self.ie_event_active_date,
            fields.Datetime.context_timestamp(self,
                                              fields.Datetime.now()))
        if self.ie_event_active_id.dian_code == '032' \
                and days_after_032 >= 3:
            note = 'Manifiesto bajo la gravedad de juramento que ' \
                'transcurridos 3 días hábiles contados desde la ' \
                'creación del Recibo de bienes y servicios {ev_id} ' \
                'con CUDE {ev_uuid}, el adquirente {adq} ' \
                'identificado con NIT {adq_vat} no manifestó expresamente ' \
                'la aceptación o rechazo de la referida factura, ' \
                'ni reclamó en contra de su contenido.'.format(
                    ev_id=self.ie_event_active_id.name,
                    ev_uuid=self.ie_event_active_id.ev_uuid,
                    adq=self.partner_id.name,
                    adq_vat=self.partner_id.vat
                )
            self = self.with_context(note_ev_034=note)
            out = self._ereignis_senden('034')
        else:
            out = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Aceptación tácita erronea.',
                    'message': 'Deben haber transcurrido 3 días hábiles '
                    'a partir de la creación del Recibo bienes y '
                    'servicios [032] sin manifiesto de aceptación o rechazo '
                    'por parte del adquiriente.',
                    'type': 'danger',
                    'sticky': True,
                }
            }
        return out

    def ablehnung(self):
        '''
        Rejection
        '''
        _logger.info('Rechazo')
        if not self.ie_claim_id:
            raise ValidationError(
                _('Debe seleccionar un concepto de rechazo para enviar '
                  'el evento de rechazo a la DIAN.'))
        out = self._ereignis_senden('031')
        return out

    def zustand_prufen(self, notif=True):
        '''
        Check status
        '''
        exe_env = self.company_id.target_environment_id
        uuid = self.fe_cufe_cude_ref
        if self.move_type in ('in_invoice', 'in_refund'):
            uuid = self.uuid_ei_ref
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
                                     'para la factura %s', self.name),
                        'type': 'warning',
                        'sticky': True,
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }
        # _logger.info('Comprobar estado')

    def _write_status_check_event(self, antwort):
        self.ensure_one()
        zustand_kod = antwort.get('zustand_kod', 'other')
        # zustand_botschaft = antwort.get('zustand_beschreiben', '')
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
        to_write = {
            'ev_fe_state': zustand_kod,
            'ev_fe_response': bild,
        }
        self.write(to_write)

    def ereignis_status_erhalten(self, exe_env):
        '''
        request the status AR
        '''
        self.ensure_one()
        wsdl = DIAN['wsdl-hab']
        if exe_env == '1':
            wsdl = DIAN['wsdl']
        art = 'abfrage_ev'
        # if not self.ie_event_status or self.ie_event_status == '04':
        #     art = 'abfrage'
        anfrage = self._bring_anfrage_unterzeichnet(exe_env,
                                                    wsdl,
                                                    art,
                                                    False)
        antwort = post(
            wsdl,
            headers={
                'content-type': 'application/soap+xml;charset=utf-8'
            },
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

    def ereignisverlauf_erstellen(self, werte=False,
                                  ar_b64=False, ev_data=False,
                                  ev_b64=False, event_code=False):
        '''
        Create the event history
        '''
        self.ensure_one()
        history_obj = self.env['history.dian.event']
        history_id = False
        resp_code = werte.get('response_code')
        # last_event_id2 = self.ie_event_history_ids.sorted(
        #       key=lambda e: e.id, reverse=True)
        last_event_id = self.ie_event_history_ids.filtered(
            lambda e: e.ev_active)
        if last_event_id and last_event_id[0].dian_code == resp_code:
            ev_status = last_event_id[0].dian_code
            date_reg = last_event_id[0].dian_date_event
        elif werte and not werte.get('event_empty', False) \
            and (not last_event_id \
                 or resp_code != last_event_id[0].dian_code \
                    or resp_code == '04'):
            date_reg = False
            if werte.get('event_date'):
                date_reg = '%s %s' % (
                    werte.get('event_date'),
                    werte.get('event_time')
                )
                date_reg = (
                    datetime.strptime(
                        date_reg,
                        '%Y-%m-%d %H:%M:%S-05:00') + timedelta(hours=5)
                ).strftime('%Y-%m-%d %H:%M:%S')

            h_val = {
                'exe_env': werte.get('exe_env'),
                # Dian
                'dian_number': werte.get('event_id'),
                'dian_uuid': werte.get('uuid'),
                'dian_date_event': date_reg,
                'dian_code': werte.get('response_code'),
                'dian_name': werte.get('response_desc'),
                'dian_ar_file': ar_b64,
                'dian_ar_fname': 'ApplicationResponseDIAN.xml',
                'dian_ar_json': self._dict_pretty_format_str(werte),
                # Event
                'name': ev_data and ev_data.get('event_id') \
                    or werte.get('ref_id'),
                'ev_uuid': ev_data and ev_data.get('uuid') \
                    or werte.get('ref_uuid'),

                'move_id': self.id,
                'ev_active': True,
            }
            if ev_data:
                ev_id = self.env['dian.event'].search(
                    [('dian_code', '=', ev_data.get('response_code'))],
                    limit=1
                )
                h_val = dict(h_val, **{
                    'ev_code': ev_data.get('response_code'),
                    'ev_id': ev_id and ev_id.id or False,
                    'ev_ar_file': ev_b64,
                    'ev_ar_fname': ev_data.get('ar_fname') \
                        or 'ApplicationResponseEvent.xml',
                    'notes': '<br/>'.join([n for n in ev_data.get('note')])
                })
            self.ie_event_history_ids.write({
                'ev_active': False
            })
            history_id = history_obj.create(h_val)
            ev_status = history_id.dian_code
        else:
            ev_status = 'other'
            if self.ev_fe_state == '67':
                ev_status = '67'
            date_reg = False
        self.write({
            'ie_event_status': ev_status,
            'ie_event_display': ev_status,
            'ie_event_active_date': date_reg
        })
        return history_id

    def _dict_pretty_format_str(self, dict_val):
        '''
        Return the dict variable in json format.
        '''
        json_val = json.dumps(dict_val, indent=4, ensure_ascii=False)
        out = '%s' % json_val
        return out

    def _reshnugnsdaten_abrufen(self):
        '''
        Get values from referenced invoice
        '''
        self.ensure_one()
        out = {}
        if self.move_type in ('in_invoice', 'in_refund'):
            doc_type = self.fe_type_ei_ref
            algoritm = doc_type in ('01', '02', '03', '04') \
                and 'CUFE-SHA384' \
                    or 'CUDE-SHA384'
            out = {
                'ID': self.name_ei_ref,
                'UUID_Algoritm': algoritm,
                'UUID': self.uuid_ei_ref,
                'DocTypeCode': doc_type,
            }
            _logger.info('Factura de proveedor referenciada')
        elif self.move_type in ('out_invoice', 'out_refund'):
            doc_type = self.fe_type
            algoritm = doc_type in ('01', '02', '03', '04') \
                and 'CUFE-SHA384' \
                    or 'CUDE-SHA384'
            out = {
                'ID': self.name,
                'UUID_Algoritm': algoritm,
                'UUID': self.fe_cufe_cude_ref,
                'DocTypeCode': doc_type,
            }
            _logger.info('Factura de proveedor referenciada')
        return out

    def _daten_fur_ereignis_abrufen(self, event, claim=False):
        '''
            Data event
            return: {}
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
        exe_env = self.company_id.target_environment_id  # TODO
        biller = self.company_id.partner_id
        # TODO: Definir quien es el receptor del evento
        receiver = self.partner_id
        person = self.ev_fe_user_id and self.ev_fe_user_id.partner_id or self.env.user.partner_id
        SoftId = self.company_id.software_id
        SoftPin = self.company_id.software_pin

        date_now = fields.Datetime.context_timestamp(self, datetime.now())
        NumDoc = self.env['ir.sequence'].next_by_code('ei.event.sequence')
        FecDoc = date_now.strftime('%Y-%m-%d')
        HorDoc = date_now.strftime('%H:%M:%S-05:00')
        #  TODO: Definir el doc referenciado
        ref_ei = self._reshnugnsdaten_abrufen()
        # RefDocTypeCode = False
        sscode = satz.ssc_erhalten(SoftId,
                                   SoftPin,
                                   NumDoc)
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
        # TODO: Definir las notas
        notes = []
        # TODO: extraer datos de factura referenciada
        # ref_ei = self._reshnugnsdaten_abrufen()
        sender_party = satz.escape_xml(biller._ar_personendetails_erhalten())
        receiver_party = satz.escape_xml(receiver._ar_personendetails_erhalten())

        werte = {
            'ProviderIDschemeID': biller.l10n_co_verification_code,
            'ProviderIDschemeName':
            biller.l10n_latam_identification_type_id.dian_code,
            'ProviderID': biller.vat,
            'SoftwareID': SoftId,
            'SoftwareSecurityCode': sscode['SSC'],
            'QRCode': QRCodeURL,  # TODO
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
            if not self.ie_claim_id:
                raise ValidationError(
                    _('Se debe seleccionar un "Concepto de rechazo" para '
                      'eviar el evento de Rechazo de esta factura.'))
            werte = dict(werte, **{
                'EventListID': self.ie_claim_id.dian_code,
                'EventListName': self.ie_claim_id.name,
            })
        elif event == '034':
            txt_ev = self._context.get('note_ev_034')
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
        Render and sign event xml
        '''
        self.ensure_one()
        unsigned_xml = satz.render_xml_edi(
            werte,
            'AppDocEvent'
        )
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
        Send Event request to DIAN
        '''
        self.ensure_one()
        wsdl = DIAN['wsdl-hab']
        anfrageart = 'SendEventUpdateStatus'
        exe_env = self.company_id.target_environment_id
        if exe_env == '1':
            wsdl = DIAN['wsdl']
        vals_to_zip = [(self._get_edi_filenames('ar'),
                        b64encode(xml))]
        xml_zip = satz.get_zipped_file(vals_to_zip)

        SendEvent_werte = self._xml_soap_werte_erhalten()
        SendEvent_werte['contentFile'] = b64encode(
            xml_zip).decode('utf-8', 'ignore')
        SendEvent_werte['To'] = wsdl.replace('?wsdl', '')
        signiert_xml = satz.get_xml_soap_with_signature(
            satz.render_xml_edi(
                SendEvent_werte,
                'SendEventUpdateStatus'
            ),
            SendEvent_werte['Id'],
            self.company_id.certificate_file,
            self.company_id.certificate_password
        )
        anfrage = etree.tostring(
            signiert_xml,
            encoding='unicode'
        )
        _logger.info('********************** SendEventUpdateStatus')
        try:
            antwort = post(
                wsdl,
                headers={
                    'content-type': 'application/soap+xml;charset=utf-8'
                },
                data=anfrage
            )
            if antwort.status_code == 200:
                daten_antwort = satz.datenantwort_erhalten(antwort)
                # self.write({'state': 'gesendet'})
                self.versandlog_erstellen(
                    anfrageart, daten_antwort, anfrage, exe_env)
                daten_antwort = dict(daten_antwort, **{
                    'ar_fname': vals_to_zip[0][0]
                })
                return daten_antwort
            elif antwort.status_code in (500, 503, 507):
                # self.write({'state': 'fehler'})
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

    def die_ereignisantwort_verarbeiten(self, antwort, ev_xml,
                                        exe_env, ev_code):
        '''
        Process the event response
        '''
        self.ensure_one()
        # titles = dict(EVENT_CODES)
        zustand_kod = antwort.get('zustand_kod', 'other')
        # zustand_botschaft = antwort.get('zustand_beschreiben', '')
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
        to_write = {
            'ev_fe_state': zustand_kod,
            'ev_fe_response': bild,
        }
        self.write(to_write)
        ar_b64 = antwort.get('xml_base64')
        ar_xml = b64decode(ar_b64).decode()
        ar_data = satz.daten_aus_ar_extrahieren(ar_xml)
        ev_b64 = b64encode(ev_xml)
        ev_data = satz.daten_aus_ar_extrahieren(ev_xml)
        ev_data['ar_fname'] = antwort.get('ar_fname')
        event_log_id = self.ereignisverlauf_erstellen(
            ar_data, ar_b64, ev_data, ev_b64, ev_code)
        if event_log_id and zustand_kod == '00':
            ad_b64 = self._ereignis_xml_ad_generieren(event_log_id)
            ad_fname = self._get_edi_filenames('ad')
            event_log_id.write({
                'ad_file': ad_b64,
                'ad_fname': ad_fname,
                'zip_file': b64encode(
                    satz.get_zipped_file([(ad_fname, ad_b64)])),
                'zip_fname': self._get_edi_filenames('zip')
            })
            self.ereignismailaktion_senden(event_log_id)
        return True

    def ereignismailaktion_senden(self, event_log_id=False):
        '''
        Send email notification for event
        '''
        self.ensure_one()
        msg = _('No hay un registro de evento para adjuntar al correo.')
        if not event_log_id:
            raise UserError(msg)

        template_id = self.env.ref(
            'l10n_co_bloodo.dian_event_email_template')

        zip_attachment = False
        if event_log_id.zip_file:
            zip_attachment = self.env['ir.attachment'].create({
                'name': event_log_id.zip_fname,
                'type': 'binary',
                'datas': event_log_id.zip_file
            })
            if zip_attachment:
                template_id.sudo().attachment_ids = [(6, 0, [zip_attachment.id])]
            else:
                template_id.sudo().attachment_ids = [(5, 0, 0)]
        template_id.send_mail(self.id, force_send=True)
        # self.write({'mail_sent': True})
        return True

    def _ereignis_xml_ad_generieren(self, ev_log_id=False):
        '''
            Return base64 from AttachedDocument file generated
        '''
        self.ensure_one()
        biller = self.company_id.partner_id
        receiver = self.partner_id
        ev_file = b64decode(ev_log_id.ev_ar_file)
        ar_file = b64decode(ev_log_id.dian_ar_file)
        werte = {
            'xml_file': ev_file.decode(),
            'ApplicationResponse': ar_file.decode(),
            'type_doc': 'evento',
        }
        parser = etree.XMLParser(remove_blank_text=True, remove_comments=True)
        ev_file = etree.fromstring(ev_file, parser=parser)
        ar_file = etree.fromstring(ar_file, parser=parser)
        ns_ev = self._get_ubl_namespaces(ev_file)
        ns_ar = self._get_ubl_namespaces(ar_file)
        # Ambiente
        werte['ProfileExecutionID'] = self._find_value(
            'cbc:ProfileExecutionID', ev_file, ns_ev)
        # Consecutivo del evento aunque puede ser generado por uno mismo
        werte['ID'] = self._find_value('cbc:ID', ev_file, ns_ev)
        werte['UUID'] = self._find_value('cbc:UUID', ev_file, ns_ev)
        time_now = fields.Datetime.context_timestamp(self,
                                                     fields.Datetime.now())
        werte['IssueDate'] = time_now.strftime('%Y-%m-%d')
        werte['IssueTime'] = time_now.strftime('%H:%M:%S-05:00')
        werte['SenderParty'] = biller._ar_personendetails_erhalten()
        werte['ReceiverParty'] = receiver._ar_personendetails_erhalten()
        werte['ValidationResultCode'] = self._find_value(
            'cac:DocumentResponse/cac:Response/cbc:ResponseCode',
            ar_file,
            ns_ar
        )
        werte['ValidationDate'] = self._find_value(
            'cbc:IssueDate', ar_file, ns_ar)
        werte['ValidationTime'] = self._find_value(
            'cbc:IssueTime', ar_file, ns_ar)

        xml_file = satz.render_xml_edi(werte,
                                       'attachment').encode()
        return b64encode(xml_file)  # .decode('utf-8', 'ignore')

    def unlink(self):
        for record in self:
            record.ie_event_history_ids.unlink()
            record.fe_log_ids.unlink()
        return super(AccountMove, self).unlink()

    def _get_business_days(self, date_init, date_end):
        resource_calendar_id = self.company_id.resource_calendar_id
        diff_date = resource_calendar_id.get_work_duration_data(date_init,
                                                                date_end)
        return diff_date.get('days')

    def cron_event_process(self, total=100):
        move_obj = self.env['account.move']
        limit_total = int(total/2)
        doc_out_ids = move_obj.search(
            [('move_type', 'in', ('out_invoice',)),
             ('fe_state', '=', '00'),
             ('way_to_pay', '=', 'credit'),
             ('ie_event_display', 'not in', ('031', '033', '034')),
             ('ev_check_date', '!=', fields.Date.today()), ],
            limit=limit_total
        )
        doc_in_ids = move_obj.search(
            [('move_type', 'in', ('in_invoice',)),
             ('fe_type_ei_ref', 'in', ('01', '02', '03', '04')),
             ('way_to_pay', '=', 'credit'),
             ('uuid_ei_ref', '!=', False),
             ('ie_event_display', 'not in', ('031', '033', '034')),
             ('ev_check_date', '!=', fields.Date.today()), ],
            limit=limit_total
        )
        doc_ok = 0
        doc_error = 0
        for doc_id in doc_out_ids + doc_in_ids:
            try:
                doc_id.zustand_prufen(notif=False)
                if doc_id.move_type in ('out_invoice', 'out_refund') \
                        and doc_id.ie_event_display == '032':
                    date_now = fields.Datetime.context_timestamp(
                        doc_id,
                        fields.Datetime.now())
                    days_after_032 = doc_id._get_business_days(
                        doc_id.ie_event_active_date,
                        date_now)
                    if days_after_032 >= 3:
                        doc_id.stillschweigende_ahnname()
                doc_ok += 1
            except Exception as error:
                doc_error += 1
                _logger.warning([doc_id, error])
                continue
        _logger.info('\nDocs OK: %s\nDocs ERROR: %s' % (doc_ok, doc_error))

    def _get_html_field_sz(self, text=''):
        return tools.html_sanitize(text)

    def action_send_multi_to_dian(self):
        '''
        Envío masivo a la DIAN de facturas de cliente seleccionadas.
        Validaciones: solo facturas de cliente, máximo 100, no enviadas, fe_type 01/02/03.
        Muestra wizard con resultado por factura (enviada correctamente / error).
        '''
        LIMIT = 100
        # 1. Solo facturas de cliente
        not_customer = self.filtered(
            lambda m: m.move_type not in ('out_invoice', 'out_refund')
        )
        if not_customer:
            raise UserError(
                _('Solo se permiten facturas de cliente (Factura, Nota crédito/débito). '
                  'Documentos no permitidos: %s')
                % ', '.join(not_customer.mapped('name'))
            )
        # 2. Máximo 100 facturas por proceso
        if len(self) > LIMIT:
            raise UserError(
                _('Solo se permite enviar hasta %s facturas por proceso. '
                  'Seleccionó %s. Reduzca la selección.')
                % (LIMIT, len(self))
            )
        # 3 y 4: Solo no enviadas a la DIAN y fe_type 01, 02, 03
        to_send = self.filtered(
            lambda m: not m.fe_state
            and m.fe_type in ('01', '02', '03')
        )
        if not to_send:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Enviar a la DIAN'),
                    'message': _(
                        'Ninguna factura cumple los requisitos para envío: '
                        'deben estar sin enviar a la DIAN y ser tipo Factura (01), '
                        'Nota Crédito (02) o Nota Débito (03).'
                    ),
                    'type': 'warning',
                    'sticky': True,
                },
            }
        result_lines = []
        for doc in to_send:
            move_name = doc.name
            try:
                doc.rechnung_senden()
                self.env.cr.commit()
                result_lines.append((0, 0, {
                    'move_id': doc.id,
                    'move_name': move_name,
                    'success': True,
                    'message': _('Enviada correctamente'),
                }))
            except Exception as e:
                self.env.cr.rollback()
                tb = ''.join(format_exception(*exc_info()))
                _logger.error(
                    'Envío masivo DIAN: error en %s (%s): %s',
                    move_name, doc.id, tb,
                )
                result_lines.append((0, 0, {
                    'move_id': doc.id,
                    'move_name': move_name,
                    'success': False,
                    'message': str(e) or tb[:500],
                }))
        count_success = sum(1 for _ in (c for c in result_lines if c[2]['success']))
        count_failed = len(result_lines) - count_success
        result = self.env['l10n.co.bloodo.send.dian.result'].create({
            'result_line_ids': result_lines,
            'count_success': count_success,
            'count_failed': count_failed,
        })
        self.env.cr.commit()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Resultado: Envío a la DIAN'),
            'res_model': 'l10n.co.bloodo.send.dian.result',
            'res_id': result.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _eids_dokumenten_senden(self, num_fe=0, num_ds=0):
        _logger.info("EI MASSIV SENDEN: Start")
        cr = Registry(self._cr.dbname).cursor()
        self = self.with_env(self.env(cr=cr))

        edi_doc_obj = self.env['account.move']
        out_doc_ids = edi_doc_obj.search(
            [('move_type','in',('out_invoice', 'out_refund')),
             ('state','=','posted'),
             ('journal_id.is_einvoicing','=',True),
             ('company_id.type_einvoicing','=','edi_dir'),
             ('fe_state','=',False),
             ('fe_response','=',False),
             ('fe_send_later','=',True)],
            order='name',
            limit=num_fe)
        in_doc_ids = edi_doc_obj.search(
            [('move_type','in',('in_invoice','in_refund')),
             ('state','=','posted'),
             ('journal_id.is_einvoicing','=',True),
             ('company_id.type_support_doc','=','edi_dir'),
             ('fe_state','=',False),
             ('fe_response','=',False),
             ('fe_send_later','=',True)],
            order='name',
            limit=num_ds)
        try:
            for doc in out_doc_ids:
                try:
                    # doc.xml_datei_erhalten()
                    if doc.type_note in ('debit', 'credit') and doc.fe_operation_type in ('20', '30'):
                        doc_ref = doc.reversed_entry_id or doc.debit_origin_id or False
                        if doc_ref and doc_ref.fe_state != '00':
                            continue
                    if doc.fe_type in ('01', '02', '03'):
                        doc.rechnung_senden()
                    elif doc.fe_type == '04' and not doc.partner_id.dian_not_send_email:
                        doc.action_send_mail()
                    # doc.to_send = False
                    self._cr.commit()
                except Exception:
                    e = exc_info()[0]
                    tb = "".join(format_exception(*exc_info()))
                    _logger.error("MASSIV STATUS EI: ERROR %s: %s" % (str(e), tb))
                    self._cr.rollback()
            for doc in in_doc_ids:
                try:
                    if doc.move_type in ('in_refund'):
                        doc_ref = doc.reversed_entry_id or False
                        if doc_ref and doc_ref.fe_state != '00':
                            continue
                    doc.rechnung_senden()
                    # doc.to_send = False
                    self._cr.commit()
                except Exception:
                    e = exc_info()[0]
                    tb = "".join(format_exception(*exc_info()))
                    _logger.error("MASSIV STATUS DS: ERROR %s: %s" % (str(e), tb))
                    self._cr.rollback()
        finally:
            try:
                self._cr.close()
            except Exception:
                pass
        _logger.info("EI MASSIV SENDEN: End")

    @api.model_create_multi
    def create(self, vals_list):
        res = super(AccountMove, self).create(vals_list)
        for record in res:
            if record.company_id.fe_send_later \
                and record.journal_id.is_einvoicing \
                    and record.move_type in ('out_invoice', 'out_refund'):
                record.fe_send_later = True
        return res

    def get_invoice_pdf_report_attachment(self):
        if len(self) < 2 and self.invoice_pdf_report_id:
            # if the Send & Print succeeded
            return self.invoice_pdf_report_id.raw, self.invoice_pdf_report_id.name
        elif len(self) < 2 and self.message_main_attachment_id:
            # if the Send & Print failed with fallback=True -> proforma PDF
            return self.message_main_attachment_id.raw, self.message_main_attachment_id.name
        # all other cases
        report_id = self._get_einvoice_report()
        report_xmlid = report_id and report_id.get_external_id()[report_id.id] \
            or 'account.account_invoices'
        pdf_content = self.env['ir.actions.report']._render(report_xmlid, self.ids)[0]
        pdf_name = self._get_invoice_report_filename() if len(self) == 1 else "Invoices.pdf"
        return pdf_content, pdf_name
    
    def get_xml_from_dian(self):
        self.ensure_one()
        if not self.fe_cufe_cude_ref:
            raise ValidationError(
                _('No hay un CUFE de referencia para descargar el XML.'))
        uuid = self.fe_cufe_cude_ref
        xml = self.env['xml.by.document.key'].xml_erhalten(uuid=uuid)
        if 'type' in xml:
            return xml
        self.write({
            'fe_xml_file': xml.get('xml_file'),
            'fe_xml_fname': xml.get('xml_fname'),
        })
    
    def action_print_pdf(self):
        self.ensure_one()
        report_id = self._get_einvoice_report()
        return report_id and report_id.report_action(self.id) \
            or self.env.ref('account.account_invoices').report_action(self.id)
    
    def _get_einvoice_report(self):
        self.ensure_one()
        report_id = self.company_id.report_template or False
        if self.move_type == 'out_refund':
            report_id = self.company_id.report_template_nc or report_id
        if self.fe_type == '02':
            report_id = self.company_id.report_template_exp or report_id
        return report_id

    def button_draft(self):
        for move in self:
            if move.journal_id.is_einvoicing \
                and move.state == 'posted' and move.fe_state == '00' \
                        and not self.env.user.has_group('l10n_co_bloodo.group_dian_to_draft_invoice'):
                raise UserError(
                    _('No tiene permitido Restablecer a Borrador la factura electrónica '
                      '%s porque ya fue procesada correctamente ante la DIAN.\n\n'
                      'Solamente un usuario con permisos puede realizar esta acción. '
                      'Sin embargo, tenga en cuenta que las modificaciones en la '
                      'fecha de factura o montos en las lineas podrían cambiar el CUFE '
                      'y perder la trazabilidad ante la DIAN, así como presentarse '
                      'diferencias en los datos entre la factura de Odoo y la factura '
                      'electrónica enviada a la DIAN.', move.name))
        return super(AccountMove, self).button_draft()

    def dian_event_send_action(self, event='', to_process=0):
        '''
        Open wizard to send event
        '''
        event_name = dict(EVENT_CODES).get(event, 'Consultar Estado Eventos')
        moves_nv = []
        moves_v = []
        count_v = 0
        count_nv = 0
        msg = ''
        for move in self:
            is_valid, error = move.dian_event_validate_move(event)
            if not is_valid:
                moves_nv.append((0, 0, {
                    'invoice_id': move.id,
                    'error': error,
                    'url_invoice': move.company_id.get_base_url() + '/odoo/invoicing/%s' % move.id}))
                count_nv += 1
                continue
            moves_v.append(move.id)
            count_v += 1
        if not count_v and not count_nv:
            msg = 'No hay facturas seleccionadas para procesar el evento %s.' % (event_name)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Evento %s' % event_name,
                    'message': msg,
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
                'default_invoice_ids': [(6, 0, moves_v)],
                'default_error_line_ids': moves_nv,
                'default_action_todo': event,
                'default_to_process': to_process,
            },
            'target': 'new',
        }

    def dian_event_validate_move(self, event=''):
        '''
        Validate if the move is correct to send the event
        '''
        self.ensure_one()
        event_codes = dict(EVENT_CODES)
        error = []
        if self.move_type == 'in_invoice':
            if self.is_einvoicing_journal:
                error.append('- Es un Doc. Soporte, no aplica para eventos.')
            else:
                if not self.is_supplier_ei:
                    error.append('- El campo "FE Proveedor" debe estar activo.')
                if self.way_to_pay != 'credit':
                    error.append('- La forma de pago debe ser crédito.')
                if not self.uuid_ei_ref:
                    error.append('- El campo "CUFE (Ref)" debe tener el CUFE de la factura.')
                if event:
                    if not self.name_ei_ref:
                        error.append('- El campo "Ref número" debe tener el consecutivo de la factura.')
                    if not self.fe_type_ei_ref:
                        error.append('- El campo "Ref tipo" debe tener el tipo de factura electrónica.')
                    if event == '030' and self.ie_event_display not in ('02', '04', False, '67', 'other'):
                        error.append('- Tiene el evento %s.' % event_codes.get(self.ie_event_display, '-'))
                    if event == '032' and self.ie_event_display != '030':
                        error.append('- El evento previo debe ser %s.' % event_codes.get('030', '-'))
                    if event == '033' and self.ie_event_display != '032':
                        error.append('- El evento previo debe ser %s.' % event_codes.get('032', '-'))
        elif self.move_type == 'out_invoice':
            if event:
                error.append('- Evento "%s" no permitido para este documento.' % event_codes.get(event, 'Consultar estado'))
            else:
                if not self.is_einvoicing_journal:
                    error.append('- El diario no está activo para facturación electrónica.')
                if self.fe_state != '00':
                    error.append('- La factura no esta procesada correctamente ante la DIAN.')
                if not self.fe_cufe_cude_ref:
                    error.append('- El campo "CUFE/CUDE" debe tener el CUFE de la factura electrónica.')
        else:
            error.append('- Los eventos DIAN no aplican para Notas Credito o Asientos.')
        if error:
            return False, '\n'.join(error)
        else:
            return True, ''

    def _dian_event_process_pending(self, batch_commit=1):
        '''
        Process the event for the invoices selected
        '''
        start_time = time.perf_counter()
        qty_total = len(self)
        qty_ok = 0
        qty_error = 0
        for index, move in enumerate(self, 1):
            try:
                if 'pending' not in move.ie_event_display:
                    continue
                event = move.ie_event_display.replace('pending', '')
                todo = '_ereignis_senden' if event else 'zustand_prufen'
                
                with self.env.cr.savepoint():
                    out = getattr(move, todo)(event)
                    qty_ok += 1
            except Exception as error:
                _logger.warning([move, error])
                with self.env.cr.savepoint():
                    move.write({
                        'ie_event_display': 'other',
                        'ev_fe_state': 'other',
                        'ev_fe_response': 'Error enviando el evento %s: \n%s' % (dict(EVENT_CODES).get(event, 'Consultar estado'), str(error)),
                    })
                    qty_error += 1
            if index % batch_commit == 0:
                self.env.cr.commit()
        self.env.cr.commit()
        time_total = time.perf_counter() - start_time
        time_avg = time_total / qty_total if qty_total else 0
        _logger.info('Eventos pendientes procesados: %s de %s. Errores: %s', qty_ok, qty_total, qty_error)
        return {
            'total': qty_total, 
            'ok': qty_ok, 
            'error': qty_error,
            'time_total': round(time_total, 2),
            'time_avg': round(time_avg, 2)
        }
