# -*- coding: utf-8 -*-

import logging
from pytz import timezone
from base64 import b64encode
from datetime import datetime
from . import ir_sentences as satz
from requests import post, exceptions

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

RESPONSE = {
    '00': 'Procesado Correctamente',
    '66': 'NSU no encontrado',
    '90': 'TrackId no encontrado',
    '99': 'Validaciones contienen errores en campos mandatorios',
    'other': 'Otro'
}

TYPE_DS = {
    'in_invoice': '05',
    'in_refund': '95'
}

DIAN_DS = {
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


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _qrcode_ds_erhalten(self, NumDS, FecDS, HorDS, NumSNO, DocABS, ValDS,
                            ValIva, ValTolDS, UUID, url):
        qr_data = 'NA'
        if NumDS:
            qr_data = 'NumDS: {}'.format(NumDS or 'NO_VALIDADO')
            qr_data += '\nFecDS: {}'.format(FecDS or '-')
            qr_data += '\nHorDS: {}'.format(HorDS or '-')
            qr_data += '\nNumSNO: {}'.format(NumSNO or '-')
            qr_data += '\nDocABS: {}'.format(DocABS or '-')
            qr_data += '\nValDS: {:.2f}'.format(ValDS)
            qr_data += '\nValIva: {:.2f}'.format(ValIva)
            qr_data += '\nValTolDS: {:.2f}'.format(ValTolDS)
            qr_data += '\nCUDS: {}'.format(UUID or '-')
            qr_data += '\nQRCode: {}'.format(url or '-')

        qr_image = satz.qrcode_erzeugen(qr_data)
        return {
            'qr_image': qr_image,
            'qr_data': qr_data
        }

    def xml_datei_erhalten_ds(self):
        self.ensure_one()
        type_doc = self._get_type_document_ds()
        xml_fname = self.fe_xml_fname \
            and self.fe_xml_fname \
                or self._get_edi_filenames_ds(type_doc)
        zip_fname = self.fe_zip_fname \
            and self.fe_zip_fname \
                or self._get_edi_filenames_ds('zip')
        ar_fname = self.fe_ar_fname \
            and self.fe_ar_fname \
                or self._get_edi_filenames_ds('ars')
        # ad_fname = self.fe_ad_fname and \
        #     self.fe_ad_fname or \
        #     self._get_edi_filenames_ds('ad')

        xml_str = self._get_xml_edi_file_ds(type_doc)
        xml_file = b64encode(xml_str)
        data_to_zip = [(xml_fname, xml_file)]
        zip_file = b64encode(satz.get_zipped_file(data_to_zip))
        # name_pdf = TYPE_DOC_NAME.get(type_doc, _('Documento'))

        self.write({
            'fe_xml_file': xml_file,
            'fe_xml_fname': xml_fname,
            'fe_zip_fname': zip_fname,
            'fe_zip_file': zip_file,
            'fe_ar_fname': ar_fname,
            # 'fe_ad_fname': ad_fname,
            # 'fe_pdf_fname': '%s %s.pdf' % (name_pdf, self.name)
        })

    def _get_type_document_ds(self):
        '''
            Return: 'invoice' or 'credit' from the type purchase document
        '''
        self.ensure_one()
        if self.move_type == 'in_invoice':
            return 'invoice'
        elif self.move_type == 'in_refund':
            return 'credit'
        else:
            return False

    def _get_edi_filenames_ds(self, type_doc=''):
        '''
            Calculates the name of the supporting document files.
            Chapter. 8.4
            - dsnnnnnnnnnnpppaadddddddd.xml - Supporting Doc.
            - nasnnnnnnnnnnpppaadddddddd.xml - Supporting Doc. Ajusting Note
            - arsnnnnnnnnnnpppaadddddddd.xml - Application Response Supporting
            - znnnnnnnnnnpppaadddddddd.zip - Zip fila supporting doc.
        '''
        self.ensure_one()
        prefix = ''
        nnnnnnnnnn = ''
        ppp = '000'
        aa = ''
        dddddddd = ''
        ext = '.xml'
        aa = fields.Datetime.context_timestamp(self,
                                               datetime.now()
                                               ).strftime('%y')
        if self.company_id.partner_id.vat:
            nnnnnnnnnn = self.company_id.partner_id.vat.zfill(10)
        else:
            raise ValidationError(
                _('El documento de identificación de %s no está establecido. \n',
                  self.company_id.partner_id.name))
        if type_doc == 'invoice':
            prefix = 'ds'
            dddddddd = self.sudo().company_id.ds_sent + 1
            self.sudo().company_id.ds_sent = dddddddd
        elif type_doc == 'credit':
            prefix = 'nas'
            dddddddd = self.sudo().company_id.nas_sent + 1
            self.sudo().company_id.nas_sent = dddddddd
        elif type_doc == 'ars':
            prefix = 'ars'
            dddddddd = self.sudo().company_id.ars_sent + 1
            self.sudo().company_id.ars_sent = dddddddd
        elif type_doc == 'zip':
            prefix = 'z'
            ext = '.zip'
            dddddddd = self.sudo().company_id.zip_sent + 1
            self.sudo().company_id.zip_sent = dddddddd
        else:
            raise ValidationError(
                _('ERROR: No se puede definir el tipo de documento '
                  'electrónico de esta factura de compra.'))
        dddddddd = '{:08x}'.format(dddddddd).upper()
        nnnnnnnnnnpppaadddddddd = nnnnnnnnnn + ppp + aa + dddddddd
        return prefix + nnnnnnnnnnpppaadddddddd + ext

    def _get_xml_edi_file_ds(self, type_doc=''):
        self.ensure_one()
        if type_doc == 'invoice':
            doc_values = self._get_values_ds_edi(type_doc)
            doc_template = 'DSInvoice'
        elif type_doc == 'credit':
            doc_values = self._get_values_nas_edi(type_doc)
            doc_template = 'DSCreditNote'
        else:
            raise ValidationError(
                _('ERROR: No se puede definir el tipo de '
                  'documento electrónico de esta factura de compra'))
        unsigned_xml = satz.render_xml_edi(doc_values,
                                           doc_template)
        xml_mit_signatur = satz.xml_mit_signatur_erhalten(
            unsigned_xml,
            self.company_id.signature_policy_url,
            self.company_id.signature_policy_description,
            self.company_id.signature_policy_file,
            self.company_id.certificate_file,
            self.company_id.certificate_password)
        return xml_mit_signatur

    def _get_values_ds_edi(self, type_doc=False):
        self.ensure_one()
        werte = self._datenwerte_erhalten_ds(type_doc)
        # werte['CustomizationID'] = self.fe_operation_type
        # # active_resolution = self._aktive_auflosung_erhalten()
        # # werte['InvoiceControl'] = active_resolution
        # werte['InvoiceTypeCode'] = self.fe_type
        # # werte['InvoiceLines'] = self._linienwerte_ds_erhalten()
        return werte

    def _get_values_nas_edi(self, type_doc=''):
        self.ensure_one()
        werte = self._datenwerte_erhalten_ds(type_doc)
        if self.is_external_invoice:
            billing_ref = {'ID': self.name_ei_ref or '',
                           'UUID': self.uuid_ei_ref or '',
                           'IssueDate': self.issue_date_ei_ref or '',}
        elif self.reversed_entry_id:
            billing_ref = self._get_ds_reference()
        else:
            billing_ref = {'ID': False,
                           'UUID': False,
                           'IssueDate': False}
        werte['BillingReference'] = billing_ref
        werte['DiscrepancyReferenceID'] = billing_ref['ID']
        werte['DiscrepancyResponseCode'] = self.fe_correction_id.dian_code
        werte['DiscrepancyDescription'] = self.fe_correction_id.name
        return werte

    def _datenwerte_erhalten_ds(self, type_doc=''):
        self.ensure_one()
        active_resolution = self._aktive_auflosung_erhalten()
        # Provedor (Sujeto no obligado)
        supplier = self.partner_id
        if not supplier:
            raise ValidationError(
                _('Es requerido relacionar al proveedor con la factura '
                  'para generar el documento soporte.'))
        # Adquiriente (ABS emisor del ds)
        customer = self.company_id.partner_id
        IdSoftware = self.company_id.ds_software_id
        AcSupplierParty = satz.escape_xml(supplier._personendetails_erhalten())
        AcCustomerParty = satz.escape_xml(customer._personendetails_erhalten())
        is_resident = '11'
        if AcSupplierParty.get('CountryIdCode') == 'CO':
            is_resident = '10'
            AcSupplierParty['CompanyIDschemeName'] = '31'
            AcSupplierParty['CompanyIDschemeID'] = supplier._get_verification_code(AcSupplierParty.get('CompanyID'))
        trm_data = self._get_payment_exchange_rate('fe')
        trm = trm_data.get('SourceCurrencyBaseRate', 1)
        InvoiceLines = self._linienwerte_ds_erhalten(trm)
        edi_taxes = self._header_steuern_ds_erhalten(trm)
        edi_taxes = self._validate_taxes(edi_taxes, InvoiceLines)
# TODO: validar a qué fecha hace referencia
        self.fe_datetime_invoice = datetime.now()
        date_format = str(self.create_date)[0:19]
        create_date = datetime.strptime(date_format, '%Y-%m-%d %H:%M:%S')
        create_date = create_date.replace(tzinfo=timezone('UTC'))

        NumDS = self.name
        FecDS = self.invoice_date.strftime('%Y-%m-%d')
        HorDS = create_date.astimezone(
            timezone('America/Bogota')).strftime('%H:%M:%S-05:00')
        ValDS = self.amount_untaxed * trm
# TODO: Validar Impuestos VOY AQUI
        ValImp1 = '01' in edi_taxes['TaxesTotal'] \
            and edi_taxes['TaxesTotal']['01']['total'] or 0
        ValTot = ValDS + ValImp1
        NitABS = customer.vat
        NumSNO = supplier.vat
        # ClTec_SoftPIN = False
        exe_env = self.company_id.ds_target_environment_id

        # if self.move_type == 'in_invoice':
        #     ClTec_SoftPIN = active_resolution['technical_key']
        # else:
        SoftPIN = self.company_id.ds_software_pin

        cufe_cude = satz.get_cufe_cude([NumDS, FecDS, HorDS,
                                        str('{:.2f}'.format(ValDS)),
                                        '01', str('{:.2f}'.format(ValImp1)),
                                        str('{:.2f}'.format(ValTot)),
                                        NumSNO, NitABS, SoftPIN, exe_env])
        sscode = satz.ssc_erhalten(IdSoftware, SoftPIN, NumDS)
        if exe_env == '1':
            QRCodeURL = DIAN_DS['catalogo']
        else:
            QRCodeURL = DIAN_DS['catalogo-hab']
        QRCodeURL = QRCodeURL.format(cufe_cude['uuid'])

        # El valor a pagar puede verse afectado, por anticipos,
        # y descuentos y cargos a nivel de factura
        PayableAmount = ValTot

        qrcode_data = self._qrcode_ds_erhalten(
            NumDS=NumDS, FecDS=FecDS, HorDS=HorDS, NumSNO=NumSNO,
            DocABS=NitABS, ValDS=ValDS, ValIva=ValImp1, ValTolDS=ValTot,
            UUID=cufe_cude['uuid'], url=QRCodeURL)

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
            'ProviderIDschemeID': customer.l10n_co_verification_code,
            'ProviderIDschemeName': \
            customer.l10n_latam_identification_type_id.dian_code,
            'ProviderID': NitABS,
            'SoftwareID': IdSoftware,
            'SoftwareSecurityCode': sscode['SSC'],
            # QRCode
            'QrCode': qrcode_data['qr_data'],
            'NitAdquiriente': NumSNO,
            'QRCodeURL': QRCodeURL,

            'CustomizationID': is_resident,
            'ProfileExecutionID': exe_env,
            'ID': NumDS,
            'UUID': cufe_cude['uuid'],
            'IssueDate': FecDS,
            'IssueTime': HorDS,
            'DueDate': self.invoice_date_due,
            'ValImp1': '{:.2f}'.format(ValImp1),
            'InvoiceTypeCode': TYPE_DS.get(self.move_type, 'false'),
            'Note': '',
            'LineCountNumeric': len(
                self.invoice_line_ids.filtered(
                    lambda l: l.display_type not in ('line_section', 'line_note'))),
            'DocumentCurrencyCode': 'COP', # self.currency_id.name,
            'OrderReference': {'ID': '',
                               'IssueDate': ''},
            'AccountingSupplierParty': AcSupplierParty,
            'AccountingCustomerParty': AcCustomerParty,
            'PaymentMeansID': self._get_payment_mean_edi(),
            'PaymentMeansCode': self.fe_payment_option_id \
                and self.fe_payment_option_id.dian_code or '1',
            'PaymentDueDate': self.invoice_date_due,
            'PaymentExchangeRate': trm_data, # self._get_payment_exchange_rate('fe'),
            'TaxesTotal': edi_taxes['TaxesTotal'],
            'WithTaxesTotal': edi_taxes['WithTaxesTotal'],
            'LineExtensionAmount': '{:.2f}'.format(ValDS),
            'TaxExclusiveAmount': '{:.2f}'.format(ValDS),
            'TaxInclusiveAmount': '{:.2f}'.format(ValTot),
            'PayableAmount': '{:.2f}'.format(PayableAmount),
            'Lines': InvoiceLines,
        }

    def die_antwort_verarbeiten_sd(self, antwort, exe_env):
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
            url = exe_env == '1' and DIAN_DS['catalogo'] \
                or DIAN_DS['catalogo-hab']
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
            # to_write['fe_cufe_cude_ref'] = cufe
        # TODO
        # # if url:
        # #     to_write['fe_url'] = url
        # TODO: Validar si en DS hay attachedDocument
        # if fe_ar_file:
        #     to_write['fe_ad_file'] = self._xml_ad_generieren()

        # to_write['fe_zip_file'] = b64encode(
        #     self._get_zipped_file(mit_pdf=True)
        # ).decode("utf-8", "ignore")
        self.write(to_write)
        # TODO: Validar si es necesario enviar un email y a quien
        # if zustand_kod == '00' and not self.mail_sent:
        #     self.action_send_mail()
        return True

    def _header_steuern_ds_erhalten(self, rate=1):
        taxes = {}
        withholding_taxes = {}
        # Trm
        # rate = 1
        # company_currency = self.company_id.currency_id
        date = fields.Date.context_today(self)

        for line in self.line_ids.filtered(lambda ln: ln.tax_line_id
                and ln.display_type not in ('line_section', 'line_note')):
            if line.tax_line_id.dian_tax_type_id \
                    and line.tax_line_id.dian_tax_type_id.dian_code:
                if line.tax_line_id.dian_tax_type_id.dian_code not in ('01', '05', '06'):
                    continue

                is_withholding = line.tax_line_id.dian_tax_type_id.retention

                if is_withholding and line.tax_line_id.amount == 0:
                    raise UserError(
                        _('El importe de la retención "%s" es igual a '
                          'cero (0). La retención debe tener monto '
                          'diferente a cero (0).', line.tax_line_id.name))
                elif is_withholding and line.tax_line_id.amount < 0:
                    withholding_taxes = line._get_taxes_line_edi(
                        withholding_taxes, line.tax_line_id,
                        rate, 'header', 'ds')
                elif is_withholding and line.tax_line_id.amount > 0:
                    # INFO  Las retenciones se recomienda
                    #       no enviarlas a la DIAN.
                    #       Solo las positivas que indican una autoretencion.
                    pass
                # XXX
                elif not is_withholding and line.tax_line_id.amount < 0:
                    raise UserError(
                        _('El importe del impuesto "%s" es negativo, '
                          'los impuestos deben tener un monto '
                          'mayor o igual a cero (0).', line.tax_line_id.name))
                elif not is_withholding and line.tax_line_id.amount > 0:
                    taxes = line._get_taxes_line_edi(taxes, line.tax_line_id,
                                                     rate, 'header', 'ds')
            else:
                raise UserError(
                    _('El impuesto "%s", no tiene asignado el código '
                      'definido por la DIAN.', line.tax_line_id.name))

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

    def _linienwerte_ds_erhalten(self, trm=1):
        invoice_lines = {}
        count = 1
        for invoice_line in self.invoice_line_ids.filtered(
                lambda ln: ln.display_type not in ('line_section', 'line_note')):
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
            error_msg = ''
            if price_unit == 0 or quantity == 0:
                error_msg += _('- Líneas de factura con precio o cantidad '
                               'cero (0) generan rechazo en la facturación '
                               'electrónica.\n')
            # UoM
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
            invoice_lines[count]['Note'] = satz.escape_xml(invoice_line.name or '')
            invoice_lines[count]['unitCode'] = invoice_line.product_uom_id \
                and invoice_line.product_uom_id.dian_uom_id \
                    and invoice_line.product_uom_id.dian_uom_id.dian_code or ''
            invoice_lines[count]['Quantity'] = '{:.2f}'.format(
                invoice_line.quantity)
            invoice_lines[count]['LineExtensionAmount'] = '{:.2f}'.format(
                subtotal) # invoice_line.price_subtotal)
            invoice_lines[count]['InvoicePeriod'] = {
                # 'Fecha de la compra'
                'StartDate': fields.Datetime.context_timestamp(
                    self, datetime.now()).strftime('%Y-%m-%d'),
                # '1 (por operacion), 2 (acumulado semanal)'
                'DescriptionCode': '1',
                # 'Por operación o Acumulado Semanal'
                'Description': 'Por operación'
            }
            invoice_lines[count]['AllowanceCharge'] = disc_charge
            invoice_lines[count]['TaxesTotal'] = {}
            invoice_lines[count]['WithTaxesTotal'] = {}
            invoice_lines[count]['ItemDescription'] = satz.escape_xml(invoice_line.name[:290] or '')
            invoice_lines[count]['BrandName'] = satz.escape_xml(invoice_line.product_id \
                and invoice_line.product_id.dian_brand or '')
            invoice_lines[count]['ModelName'] = satz.escape_xml(invoice_line.product_id \
                and invoice_line.product_id.dian_model or '')
            invoice_lines[count]['PackSizeNumeric'] = ''
            invoice_lines[count]['SellersItemIdentification'] = \
                satz.escape_xml(invoice_line.product_id.default_code)
            invoice_lines[count]['StandardItemIdentification'] = \
                invoice_line._get_product_standard_code()
            invoice_lines[count]['PriceAmount'] = '{:.4f}'.format(price_unit)
# TODO: Validar cuales impuestos aplican para Doc Sopporte
#       y como proceder si hay impuestos diferentes y retenciones
            for tax in invoice_line.tax_ids:  # tax_line_id: # tax_ids
                if tax.amount_type == 'group':
                    tax_ids = tax.children_tax_ids
                else:
                    tax_ids = tax

                for tax_id in tax_ids:
                    if tax_id.dian_tax_type_id and tax_id.dian_tax_type_id.dian_code:
                        if tax_id.dian_tax_type_id.dian_code not in ('01','05','06'):
                            continue
                        is_withholding = tax_id.dian_tax_type_id.retention

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
                                    'ds'
                            )
                        elif is_withholding and tax_id.amount > 0:
                            pass
                        elif not is_withholding and tax_id.amount < 0:
                            raise UserError(
                                _('El importe del impuesto "%s" es negativo, '
                                  'el impuesto debe tener un monto '
                                  'mayor o igual a cero (0).', tax_id.name))
                        elif not is_withholding and tax_id.amount == 0:
                            pass
                        else:
                            invoice_lines[count]['TaxesTotal'] = \
                                invoice_line._get_taxes_line_edi(
                                    invoice_lines[count]['TaxesTotal'],
                                    tax_id,
                                    trm,
                                    'item',
                                    'ds'
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
            count += 1
        return invoice_lines

    def _get_ds_reference(self):
        billing_reference = {}
        inv_ref_id = self.reversed_entry_id or False

        if not inv_ref_id:
            raise ValidationError(
                _('No es posible identificar la factura '
                  'referencia de esta Nota.'))

        if inv_ref_id.state == 'posted':
            if inv_ref_id.fe_state == '00' or inv_ref_id.fe_send_later:
                # fe_invoice_name
                billing_reference = {
                    'ID': inv_ref_id.name,
                    'UUID': inv_ref_id.fe_cufe_cude_ref,
                    'IssueDate': inv_ref_id.invoice_date,
                }
                self.write({
                    'name_ei_ref': inv_ref_id.name,
                    'uuid_ei_ref': inv_ref_id.fe_cufe_cude_ref,
                    'issue_date_ei_ref': inv_ref_id.invoice_date
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

