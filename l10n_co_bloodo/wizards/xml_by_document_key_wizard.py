# -*- coding: utf-8 -*-

import logging
from lxml import etree
from requests import post
from base64 import b64decode, b64encode
from ..models import ir_sentences as satz
from odoo import fields, models, _
from odoo.exceptions import ValidationError

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


class XMLByDocumentKey(models.TransientModel):
    _name = 'xml.by.document.key'
    _description = 'Xml by document key'

    track_id = fields.Char('CUFE')
    company_id = fields.Many2one('res.company', 
                        'Compañía',
                        default=lambda self: self.env.company)
    xml_fname = fields.Char('Xml fname',
                        default='DocumentoXML.xml')
    xml_file = fields.Binary('Doc. XML')
    
    def xml_erhalten(self, uuid=False):
        # self.ensure_one()
        wsdl = DIAN['wsdl']
        company_id = self.company_id or self.env.company
        werte = self._xml_werte_erhalten(uuid)
        werte['To'] = wsdl.replace('?wsdl', '')
        anfrage = satz.get_xml_soap_with_signature(
            satz.render_xml_edi(
                werte,
                'GetXMLByDocumentKey'
            ),
            werte['Id'],
            company_id.certificate_file,
            company_id.certificate_password
        )
        antwort = post(
            wsdl,
            headers={
                'content-type': 'application/soap+xml;charset=utf-8'
            },
            data=etree.tostring(anfrage)
        )
        if antwort.status_code == 200:
            daten = self.datenantwort_erhalten(antwort)
            if daten.get('kod') == '100':
                xml_b64 = daten.get('xml_base64', '')
                if len(xml_b64):
                    xml = etree.fromstring(b64decode(xml_b64))
                    ns = xml.nsmap
                    ns['xmlns'] = ns.pop(None)
                    root_xml = xml.getroottree().docinfo.root_name
                    xml_name = 'cbc:ID'
                    if 'Nomina' in root_xml:
                        xml_name = 'xmlns:NumeroSecuenciaXML'
                        name = xml.xpath(f'//xmlns:{root_xml}/{xml_name}', namespaces=ns)
                        name = name and name[0].attrib.get('Numero', 'Nomina') or 'Nomina'
                        name = name + '.xml'
                    else:
                        name = xml.xpath(f'//xmlns:{root_xml}/cbc:ID', namespaces=ns)
                        name = len(name) and f'{name[0].text}.xml' or 'Documento.xml'
                    if uuid:
                        return {
                            'xml_fname': name,
                            'xml_file': xml_b64
                        }
                    self.write({
                        'xml_fname': name,
                        'xml_file': xml_b64
                    })
                else:
                    raise ValidationError(_(
                        'GetXMLByDocumentKey Error\n\n'
                        'No hay un documento xml en la respuesta.\n\n%s', antwort.text))
            else:
                _logger.warning(str(antwort.text).replace('><', '>\n<'))
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'warning',
                        'title': _('Respuesta DIAN'),
                        'message': _("Código: {}: {}").format(
                            daten.get('kod', 'Error'), 
                            daten.get('beschreiben', 'Desconocido')),
                        'sticky': True,
                    }
                }
        else:
            raise ValidationError(
                _('Error en metodo GetXMLByDocumentKey.'
                  '\nEstado: %s \nReason: %s',
                  antwort.status_code, antwort.reason))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consultar XML'),
            'view_mode': 'form',
            'res_model': 'xml.by.document.key',
            'target': 'new',
            'res_id': self.id,
        }

    def _xml_werte_erhalten(self, uuid=False):
        company_id = self.company_id or self.env.company
        uuid = uuid or self.track_id
        werte = satz.get_xml_soap_values(company_id.certificate_file,
                                         company_id.certificate_password)
        werte['trackId'] = uuid
        return werte
    
    def datenantwort_erhalten(self, antwort):
        '''
            Antwort lesen
        '''
        xmlns = 'http://wcf.dian.colombia'
        b = 'http://schemas.datacontract.org/2004/07/UploadDocumentResponse'
        ba = 'http://schemas.datacontract.org/2004/07/DianResponse'
        ca = 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'
        wurzel = etree.fromstring(antwort.text)
        ns = wurzel.nsmap
        ns['xmlns'] = xmlns
        daten = {}
        # Resultado
        ergebnis = wurzel.xpath('//xmlns:GetXmlByDocumentKeyResult', namespaces=ns)
        if ergebnis:
            ergebnis = ergebnis[0]
            ns = ergebnis.nsmap
            ns['xmlns'] = ns.pop(None)
            for artikel in ergebnis.xpath('//b:Code', namespaces=ns):
                daten['kod'] = artikel.text
            for artikel in ergebnis.xpath('//b:Message', namespaces=ns):
                daten['beschreiben'] = artikel.text
            for artikel in ergebnis.xpath('//b:ValidationDate', namespaces=ns):
                daten['datum'] = artikel.text
            for artikel in ergebnis.xpath('//b:XmlBytesBase64', namespaces=ns):
                daten['xml_base64'] = artikel.text

        if not daten:
            raise ValidationError(
                _('The DIAN response could not be processed. \n'
                'XMLresponse:\n %s', antwort.text))

        # daten = dict(daten, **{
        #     'reason': antwort.reason,
        #     'status_code': antwort.status_code,
        #     'response_text': antwort.text
        # })
        return daten