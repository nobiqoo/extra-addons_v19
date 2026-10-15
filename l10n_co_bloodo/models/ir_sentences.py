# -*- coding: utf-8 -*-

import json
import xmlsig
import hashlib
import xmltodict
from os import path
from uuid import uuid4
from lxml import etree
from io import BytesIO
from pytz import timezone
from OpenSSL import crypto
from unidecode import unidecode
from xml.sax.saxutils import escape
from qrcode import QRCode, constants
from zipfile import ZipFile, ZIP_DEFLATED
from base64 import b64encode, b64decode
from pgxades import XAdESContext, PolicyId, template
# from xades import XAdESContext, template
# from xades.policy import GenericPolicyId
from datetime import datetime, date, timedelta
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
                'xml'
            )
        )
    )
    template_xml = env.get_template('{}.xml'.format(template_name))
    xml = template_xml.render(values)

    return xml


def get_cufe_cude(list_data):
    # NumFac, FecFac, HorFac, ValFac, CodImp1, ValImp1,
    #               CodImp2, ValImp2, CodImp3, ValImp3, ValTot, NitFE,
    #               NumAdq, ClTec_SoftPIN, TipoAmbie):
    # CUFE = SHA-384(NumFac + FecFac + HorFac + ValFac + CodImp1 + ValImp1 +
    #               CodImp2 + ValImp2 + CodImp3 + ValImp3 + ValTot + NitFE +
    #               NumAdq + ClTec + TipoAmbie)
    # CUDE = SHA-384(NumFac + FecFac + HorFac + ValFac + CodImp1 + ValImp1 +
    #               CodImp2 + ValImp2 + CodImp3 + ValImp3 + ValTot + NitFE +
    #               NumAdq + Software-PIN + TipoAmbie)
    # list_data = [NumFac, str(FecFac), str(HorFac), ValFac, CodImp1, ValImp1,
    #              CodImp2, ValImp2, CodImp3, ValImp3, ValTot, NitFE, NumAdq,
    #              ClTec_SoftPIN, TipoAmbie]
    val_uncoded = '|'.join(list_data)
    val_unicode = unidecode(''.join(list_data))
    cufe_cude = hashlib.sha384(val_unicode.encode()).hexdigest()
    return {'uuid_uncoded': val_uncoded,
            'uuid': cufe_cude}


def ssc_erhalten(IdSoft, Pin, NumDoc):
    list_data = [IdSoft, Pin, NumDoc]
    val_uncoded = '|'.join(list_data)
    val_unicode = unidecode(''.join(list_data))
    ssc = hashlib.sha384(val_unicode.encode())
    return {'SSC_Uncoded': val_uncoded,
            'SSC': ssc.hexdigest()}


def xml_mit_signatur_erhalten(xml_without_signature,
                              signature_policy_url,
                              signature_policy_description,
                              signature_policy_file,
                              certificate_file,
                              certificate_password,
                              issuedate=False,
                              issuetime=False):
    # https://github.com/etobella/python-xades
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
    if issuedate and issuetime:
        ns = signature.nsmap
        ns['xades'] = 'http://uri.etsi.org/01903/v1.3.2#'
        signtime = '{}T{}'.format(issuedate, issuetime)
        signtime_nw = datetime.strptime(signtime, '%Y-%m-%dT%H:%M:%S-05:00') + timedelta(minutes=1.00131)
        signtime = signtime_nw.strftime('%Y-%m-%dT%H:%M:%S.%f-05:00')
        signature.xpath(f'//xades:SigningTime', namespaces=ns)[0].text = signtime
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
        if position == 1:
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
            _('La contraseña del certificado o el archivo del certificado '
              'no es válido.\nExcepción: %s', e))

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
    # ctx.load_pkcs12(cert)
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

    with ZipFile(output, mode='w', compression=ZIP_DEFLATED, compresslevel=9) as zf:
        for fname, fb64 in data:
            zf.writestr(fname, b64decode(fb64))

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
            '{%s}SendBillSyncResponse' % xmlns)] or \
        [element for element in wurzel.iter(
            '{%s}SendEventUpdateStatusResponse' % xmlns)] or \
        [element for element in wurzel.iter(
            '{%s}GetStatusEventResponse' % xmlns)] or \
        [element for element in wurzel.iter(
            '{%s}SendTestSetAsyncResponse' % xmlns)]
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
        'response_text': daten and etree.tostring(ergebnis, encoding='UTF-8').decode('utf-8') or antwort.text
    })
    return daten

def daten_aus_ar_extrahieren(xml):
    '''
    Daten aus der ApplicationResponse extrahieren
    '''
    if isinstance(xml, str):
        xml = xml.encode('utf-8')
    parse = etree.XMLParser(encoding='utf-8')
    xml_ar = etree.fromstring(xml, parse)
    ns_ar = xml_ar.nsmap
    ns_ar['inv'] = ns_ar.pop(None)
    doc_resp = find_element('cac:DocumentResponse', xml_ar, ns_ar, all=True)
    xml_doc_resp = len(doc_resp) and doc_resp[-1] \
        or etree.fromstring(b'<null></null>')
    line_response = find_element(
        'cac:LineResponse', xml_doc_resp, ns_ar, all=True)
    lines_resp = [{
        'id': find_value('cac:LineReference/cbc:LineID', line, ns_ar),
        'code': find_value('cac:Response/cbc:ResponseCode', line, ns_ar),
        'description': find_value('cac:Response/cbc:Description', line, ns_ar)
    } for line in line_response]
    response_code = find_element(
        'cac:Response/cbc:ResponseCode', xml_doc_resp, ns_ar)
    uuid = find_element('cac:DocumentReference/cbc:UUID',
                        xml_doc_resp,
                        ns_ar)
    out_ar = {
        'event_empty': not doc_resp and True or False,
        'exe_env': find_value('cbc:ProfileExecutionID', xml_ar, ns_ar),
        'event_id': find_value('cbc:ID', xml_ar, ns_ar),
        'uuid': find_value('cbc:UUID', xml_ar, ns_ar),
        'uuid_alg': find_element(
            'cbc:UUID', xml_ar, ns_ar).attrib.get('schemeName'),
        'event_date': find_value('cac:Response/cbc:EffectiveDate', xml_doc_resp, ns_ar),
        'event_time': find_value('cac:Response/cbc:EffectiveTime', xml_doc_resp, ns_ar),
        'event_ar_date': find_value('cbc:IssueDate', xml_ar, ns_ar),
        'event_ar_time': find_value('cbc:IssueTime', xml_ar, ns_ar),
        'note': [
            note.text
            for note in find_element('cbc:Note', xml_ar, ns_ar, all=True)
        ],
        'sender': get_data_partner(
            find_element('cac:SenderParty', xml_ar, ns_ar),
            ns_ar
        ),
        'receiver': get_data_partner(
            find_element('cac:ReceiverParty', xml_ar, ns_ar),
            ns_ar
        ),
        'response_code': response_code is not None
        and response_code.text or None,
        'response_reject_code': response_code is not None
        and response_code.get('listID') or None,
        'response_reject_name': response_code is not None
        and response_code.get('name') or None,
        'response_desc': find_value(
            'cac:Response/cbc:Description',
            xml_doc_resp,
            ns_ar
        ),
        'ref_id': find_value(
            'cac:DocumentReference/cbc:ID',
            xml_doc_resp,
            ns_ar
        ),
        'ref_uuid': uuid is not None and uuid.text or None,
        'ref_uuid_alg': uuid is not None and uuid.attrib.get('schemeName') or None,
        'ref_type_doc': find_value(
            'cac:DocumentReference/cbc:DocumentTypeCode',
            xml_doc_resp,
            ns_ar
        ),
        'lines': lines_resp,
        'person': get_person(
            find_element('cac:IssuerParty',
                         xml_doc_resp,
                         ns_ar),
            ns_ar
        )
    }
    return out_ar


def find_value(xpath, tree, namespaces):
    element = tree.xpath(xpath, namespaces=namespaces)
    return element and element[0].text or None


def find_element(xpath, tree, namespaces, all=False):
    element = tree.xpath(xpath, namespaces=namespaces)
    if element:
        return all and element or element[0]
    else:
        return [] if all else None


def get_data_partner(tree=None, namespaces=None):
    if tree is not None:
        out = {
            'name': find_value('cac:PartyTaxScheme/cbc:RegistrationName',
                               tree,
                               namespaces),
            'id': find_value('cac:PartyTaxScheme/cbc:CompanyID',
                             tree,
                             namespaces),
            'tax_id': find_value('cac:PartyTaxScheme/cac:TaxScheme/cbc:ID',
                                 tree,
                                 namespaces),
            'tax': find_value('cac:PartyTaxScheme/cac:TaxScheme/cbc:Name',
                              tree,
                              namespaces),
        }
        identify = find_element('cac:PartyTaxScheme/cbc:CompanyID',
                                tree,
                                namespaces)
        out['type_id'] = identify.attrib.get('schemeName')
        out['dv_id'] = identify.attrib.get('schemeID')
        return out
    else:
        return None


def get_person(tree, namespaces):
    if tree is not None:
        out = {
            'id': find_value('cac:Person/cbc:ID', tree, namespaces),
            'name': find_value('cac:Person/cbc:FirstName', tree, namespaces),
            'lastname': find_value('cac:Person/cbc:FamilyName', tree, namespaces),
            'job': find_value('cac:Person/cbc:JobTitle', tree, namespaces),
            'area': find_value('cac:Person/cbc:OrganizationDepartment', tree, namespaces),
        }
        identify = find_element('cac:Person/cbc:ID', tree, namespaces)
        out['type_id'] = identify is not None and identify.attrib.get('schemeName') or None
        out['dv_id'] = identify is not None and identify.attrib.get('schemeID') or None
        return out
    else:
        return None

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

def is_xml_ok(txt):
    try:
        xml = etree.fromstring(txt)
        return True
    except:
        return False

def xml_to_json(xml='', attrs=True, simple=False):
    """
    Convierte un XML a JSON.
    Si simple es True, devuelve un JSON con una estructura plana.
    """
    dict_data = xmltodict.parse(xml, attr_prefix="@", xml_attribs=attrs)  # Prefijo para distinguir atributos
    if 's:Envelope' in dict_data and 's:Body' in dict_data['s:Envelope']:
        dict_data = dict_data['s:Envelope']['s:Body']
    if simple:
        # Convertir a un formato más simple
        out = print_simple_dict(dict_data)
    else:
        out = json.dumps(dict_data, indent=4)
    return out

def print_simple_dict(dict_data, nivel=0):
    out = ''
    for key, value in dict_data.items():
        indent = "  " * nivel  # Sangría para la jerarquía
        if isinstance(value, dict):
            out += f"{indent}{key}:\n"
            out += print_simple_dict(value, nivel + 1)
        else:
            out += f"{indent}{key}:  {value}\n"
    return out