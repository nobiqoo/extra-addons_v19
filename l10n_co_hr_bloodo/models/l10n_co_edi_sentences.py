# -*- coding: utf-8 -*-

import xmlsig
import hashlib
from os import path
from uuid import uuid4
from lxml import etree
from io import BytesIO
from pytz import timezone
from OpenSSL import crypto
from unidecode import unidecode
from xml.sax.saxutils import escape
from qrcode import QRCode, constants
from zipfile import ZIP_BZIP2, ZipFile
from base64 import b64encode, b64decode
from pgxades import XAdESContext, PolicyId, template
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12, PublicFormat, PrivateFormat, NoEncryption

from odoo import _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)


# https://stackoverflow.com/questions/38432809/dynamic-xml-template-generation-using-get-template-jinja2
def render_xml_edi(values, template_name):
    base_path = path.dirname(path.dirname(__file__))
    env = Environment(
        loader=FileSystemLoader(
            path.join(
                base_path,
                'l10n_co_edi_hr_xml'
            )
        )
    )
    template_xml = env.get_template('{}.xml'.format(template_name))
    xml = template_xml.render(values)

    return xml.replace('&', '&amp;')


def cune_erhalten(NumNE, FecNE, HorNE, ValDev, ValDed, ValTolNE,
             NitNE, DocEmp, TipoXML, SoftPIN, TipAmb):
    # CUNE = SHA-384(NumNE + FecNE + HorNE + ValDev +
    #  ValDed + ValTolNE + NitNE + DocEmp + SoftPIN + TipoAmb)
    val_uncoded = '%s + %s + %s + %s + %s + ' \
                    '%s + %s + %s + %s + %s + ' \
                    '%s' % (NumNE, str(FecNE), str(HorNE),
                            ValDev, ValDed, ValTolNE,
                            NitNE, DocEmp,
                            TipoXML, SoftPIN, TipAmb)
    val_unicode = unidecode('%s%s%s%s%s%s%s%s%s%s%s' % (
                            NumNE, str(FecNE), str(HorNE),
                            ValDev, ValDed, ValTolNE,
                            NitNE, DocEmp,
                            TipoXML, SoftPIN, TipAmb))

    cune = hashlib.sha384(val_unicode.encode()).hexdigest()

    return {'CUNEUncoded': val_uncoded,
            'CUNE': cune}


def ssc_erhalten(IdSoft, Pin, NumDoc):
    val_uncoded = '%s + %s + %s' % (IdSoft, Pin, NumDoc)
    val_unicode = unidecode(IdSoft + Pin + NumDoc)
    ssc = hashlib.sha384(val_unicode.encode())
    return {'SSC_Uncoded': val_uncoded,
            'SSC': ssc.hexdigest()}


# https://github.com/etobella/python-xades
def xml_mit_signatur_erhalten(xml_without_signature,
                              signature_policy_url,
                              signature_policy_description,
                              signature_policy_file,
                              certificate_file,
                              certificate_password):
    # https://github.com/etobella/python-xades/blob/master/test/base.py
    # base_path = path.dirname(path.dirname(__file__))
    # root = etree.parse(path.join(base_path, name)).getroot()
    # https://lxml.de/tutorial.html
    parser = etree.XMLParser(remove_blank_text=True, remove_comments=True)
    root = etree.fromstring(
        xml_without_signature.encode('utf-8'),
        parser=parser
    )
    # https://github.com/etobella/python-xades/blob/master/test/test_xades.py
    signature_id = 'xmldsig-{}'.format(uuid4())
    signature = xmlsig.template.create(xmlsig.constants.TransformInclC14N,
                                       xmlsig.constants.TransformRsaSha512,
                                       signature_id)
    ref = xmlsig.template.add_reference(signature,
                                        xmlsig.constants.TransformSha512,
                                        uri='',
                                        name=signature_id + '-ref0')
    xmlsig.template.add_transform(ref,
                                  xmlsig.constants.TransformEnveloped)
    xmlsig.template.add_reference(signature,
                                  xmlsig.constants.TransformSha512,
                                  uri='#' + signature_id + '-keyinfo')
    xmlsig.template.add_reference(
        signature,
        xmlsig.constants.TransformSha512,
        uri='#' + signature_id + '-signedprops',
        uri_type='http://uri.etsi.org/01903#SignedProperties'
    )
    ki = xmlsig.template.ensure_key_info(signature,
                                         name=signature_id + '-keyinfo')
    data = xmlsig.template.add_x509_data(ki)
    xmlsig.template.x509_data_add_certificate(data)
    serial = xmlsig.template.x509_data_add_issuer_serial(data)
    xmlsig.template.x509_issuer_serial_add_issuer_name(serial)
    xmlsig.template.x509_issuer_serial_add_serial_number(serial)
    xmlsig.template.add_key_value(ki)
    qualifying = template.create_qualifying_properties(signature)
    props = template.create_signed_properties(
        qualifying,
        name=signature_id + '-signedprops'
    )
    template.add_claimed_role(props, 'supplier')
    # policy = GenericPolicyId(signature_policy_url,
    #                          signature_policy_description,
    #                          xmlsig.constants.TransformSha512)

    policy = PolicyId()
    policy.id = signature_policy_url  # config['policy_id']
    policy.name = signature_policy_description  # config['policy_name']
    # config['policy_remote'])
    policy.remote = b64decode(signature_policy_file)
    policy.hash_method = xmlsig.constants.TransformSha512

    root.append(signature)
    ctx = XAdESContext(policy)
    _key, cert, _additional_certs = get_pkcs12(certificate_file, certificate_password)
    ctx.x509 = cert
    ctx.public_key = cert.public_key()
    ctx.private_key = _key
    # with patch('xades.policy.urllib.urlopen') as mock:
    #    mock.return_value = b64decode(signature_policy_file).read()
    ctx.sign(signature)
    # ctx.verify(signature)

    # Se debe firmar en un paso anterior, y luego remover el signature para
    # ubicarlo en posicion necesaria
    root.remove(signature)
    ext = 'urn:oasis:names:specification:ubl:' \
        'schema:xsd:CommonExtensionComponents-2'
    ds = 'http://www.w3.org/2000/09/xmldsig#'
    position = 0

    # https://lxml.de/tutorial.html
    for element in root.iter('{%s}ExtensionContent' % ext):
        if position == 0:
            element.append(signature)
        position += 1

    # Complememto para añadir atributo faltante
    for element in root.iter('{%s}SignatureValue' % ds):
        element.attrib['Id'] = signature_id + '-sigvalue'

    # https://www.decalage.info/en/python/lxml-c14n
    output = BytesIO()
    root.getroottree().write_c14n(output)  # , exclusive=1, with_comments=0
    root = output.getvalue()
    return root

def get_pkcs12(certificate_file, certificate_password):
    try:
        # return crypto.load_pkcs12(
        #     b64decode(certificate_file),
        #     certificate_password.encode('utf-8'))
        return pkcs12.load_key_and_certificates(
            b64decode(certificate_file),
            certificate_password.encode('utf-8'))
    except Exception as e:
        raise ValidationError(
            _('The certificate password or certificate file is not'
              ' valid.\nException: %s') % e)


def qrcode_erzeugen(data):
    qr = QRCode(version=1,
                error_correction=constants.ERROR_CORRECT_L,
                box_size=20,
                border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image()
    # temp = StringIO()
    temp = BytesIO()
    img.save(temp, format='PNG')
    qr_img = b64encode(temp.getvalue()).decode('utf-8', 'ignore')
    return qr_img


def get_xml_soap_values(certificate_file, certificate_password):
    Created = datetime.now().replace(tzinfo=timezone('UTC'))
    Created = Created.astimezone(timezone('UTC'))
    Expires = (Created + timedelta(seconds=60000)
               ).strftime('%Y-%m-%dT%H:%M:%S.001Z')
    Created = Created.strftime('%Y-%m-%dT%H:%M:%S.001Z')
    # https://github.com/mit-dig/idm/blob/master/idm_query_functions.py#L151
    _key, cert, _additional_certsout = get_pkcs12(certificate_file, certificate_password)
    # cert = pkcs12.get_certificate()
    # der = b64encode(crypto.dump_certificate(
    #     crypto.FILETYPE_ASN1, cert)).decode('utf-8', 'ignore')
    der = b64encode(cert.public_bytes(Encoding.DER)).decode('utf-8')

    return {'Created': Created,
            'Expires': Expires,
            'Id': uuid4(),
            'BinarySecurityToken': der}


def get_xml_soap_with_signature(xml_soap_without_signature, Id,
                                certificate_file, certificate_password):
    wsse = 'http://docs.oasis-open.org/wss/2004/01/' \
        'oasis-200401-wss-wssecurity-secext-1.0.xsd'
    wsu = 'http://docs.oasis-open.org/wss/2004/01/' \
        'oasis-200401-wss-wssecurity-utility-1.0.xsd'
    X509v3 = 'http://docs.oasis-open.org/wss/2004/01/' \
        'oasis-200401-wss-x509-token-profile-1.0#X509v3'
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_soap_without_signature, parser=parser)
    signature_id = '{}'.format(Id)
    signature = xmlsig.template.create(
        xmlsig.constants.TransformExclC14N,
        xmlsig.constants.TransformRsaSha256,  # solo me ha funcionado con esta
        'SIG-' + signature_id)
    ref = xmlsig.template.add_reference(
        signature,
        xmlsig.constants.TransformSha256,
        uri='#id-' + signature_id)
    xmlsig.template.add_transform(
        ref,
        xmlsig.constants.TransformExclC14N)
    ki = xmlsig.template.ensure_key_info(
        signature,
        name='KI-' + signature_id)
    ctx = xmlsig.SignatureContext()
    _key, cert, _additional_certs = get_pkcs12(certificate_file, certificate_password)
    ctx.x509 = cert.public_bytes(Encoding.PEM)
    ctx.public_key = cert.public_key()
    ctx.private_key = _key

    for element in root.iter('{%s}Security' % wsse):
        element.append(signature)

    ki_str = etree.SubElement(
        ki,
        '{%s}SecurityTokenReference' % wsse)
    ki_str.attrib['{%s}Id' % wsu] = 'STR-' + signature_id
    ki_str_reference = etree.SubElement(
        ki_str,
        '{%s}Reference' % wsse)
    ki_str_reference.attrib['URI'] = '#X509-' + signature_id
    ki_str_reference.attrib['ValueType'] = X509v3
    ctx.sign(signature)
    ctx.verify(signature)

    return root

def get_zipped_file(data):
    '''
        Zip files
        input:
            data: [(filename, file_base64)]
    '''
    output = BytesIO()
    zipfile = ZipFile(output, mode='w')
    for fname, fb64 in data:
        zipfile_content_xml = BytesIO()
        zipfile_content_xml.write(b64decode(fb64))
        zipfile.writestr(fname, zipfile_content_xml.getvalue())
    zipfile.close()

    return output.getvalue()

def datenantwort_erhalten(antwort):
    '''
        Antwort lesen
    '''
    xmlns = 'http://wcf.dian.colombia'
    b = 'http://schemas.datacontract.org/2004/07/UploadDocumentResponse'
    ba = 'http://schemas.datacontract.org/2004/07/DianResponse'
    ca = 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'
    wurzel = etree.fromstring(antwort.text)
    daten = {}
    # test async
    for element in wurzel.iter('{%s}SendTestSetAsyncResponse' % xmlns):
        fehlerliste = []
        for fehleren in element.iter('{%s}XmlParamsResponseTrackId' % b):
            archiv = ''
            meldung = ''
            for fehler in fehleren.iter('{%s}xmlFileName' % b):
                archiv = fehler.text
            for fehler in fehleren.iter('{%s}processedMessage' % b):
                meldung = fehler.text
            fehlerliste.append((archiv, meldung))
        daten['fehlerliste'] = fehlerliste
        for zipkey in element.iter('{%s}ZipKey' % b):
            daten['zipkey'] = zipkey.text
    # Resultado
    ergebnis = \
        [element for element in wurzel.iter(
            '{%s}GetStatusResponse' % xmlns)] or \
        [element for element in wurzel.iter(
            '{%s}GetStatusZipResponse' % xmlns)] or \
        [element for element in wurzel.iter(
            '{%s}SendNominaSyncResponse' % xmlns)]
    if ergebnis:
        ergebnis = ergebnis[0]
        for fehleren in ergebnis.iter('{%s}ErrorMessage' % ba):
            fehlerliste = []
            for fehleren in fehleren.iter('{%s}string' % ca):
                fehlerliste.append(fehleren.text)
            daten['fehlerliste'] = fehlerliste
        for artikel in ergebnis.iter('{%s}IsValid' % ba):
            daten['gultig'] = artikel.text
        for artikel in ergebnis.iter('{%s}StatusCode' % ba):
            daten['zustand_kod'] = artikel.text
        for artikel in ergebnis.iter('{%s}StatusDescription' % ba):
            daten['zustand_beschreiben'] = artikel.text
        for artikel in ergebnis.iter('{%s}StatusMessage' % ba):
            daten['zustand_nachricht'] = artikel.text
        for artikel in ergebnis.iter('{%s}XmlBase64Bytes' % ba):
            daten['xml_base64'] = artikel.text
        for artikel in ergebnis.iter('{%s}XmlBytes' % ba):
            daten['xml_bytes'] = artikel.text
        for artikel in ergebnis.iter('{%s}XmlDocumentKey' % ba):
            daten['xml_dokument_schlussel'] = artikel.text
        for artikel in ergebnis.iter('{%s}XmlFileName' % ba):
            daten['xml_dateiname'] = artikel.text

    if not daten:
        raise ValidationError(
            _('The DIAN response could not be processed. \n'
              'XMLresponse:\n %s', antwort.text))

    daten = dict(daten, **{
        'reason': antwort.reason,
        'status_code': antwort.status_code,
        'response_text': antwort.text
    })
    return daten

def escape_xml(data):
    if isinstance(data, str):
        return escape(data)
    elif isinstance(data, list):
        out = []
        for d in data:
            out.append(escape_xml(d))
        return out
    elif isinstance(data, dict):
        out = {}
        for k, v in data.items():
            out[k] = escape_xml(v)
        return out
    else:
        return data
