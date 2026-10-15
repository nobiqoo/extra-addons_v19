# -*- coding: utf-8 -*-

from lxml import etree
from requests import post, exceptions

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from . import l10n_co_edi_sentences as satz

ENVIRONMENT = [
    ('1', 'Producción'),
    ('2', 'Test')
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    nie_sent = fields.Integer(string='Nóminas enviadas')
    niae_sent = fields.Integer(string='Nóminas de ajuste enviadas')
    z_sent = fields.Integer(string='Zip enviados')

    hr_certificate_filename = fields.Char(string='Nombre Certificado')
    hr_certificate_file = fields.Binary(string='NE Certificado')
    hr_certificate_password = fields.Char(string='NE Pwd Certificado')
    hr_signature_policy_url = fields.Char(string='Url Politica de firma', default='https://facturaelectronica.dian.gov.co/politicadefirma/v2/politicadefirmav2.pdf')
    hr_signature_policy_description = fields.Char(string='Descripción Política de firma', default='Política de firma para nóminas electrónicas de la República de Colombia.')
    hr_signature_policy_filename = fields.Char(string='Nombre archivo política de firma')
    hr_signature_policy_file = fields.Binary(string='Política de firma')

    hr_target_environment = fields.Selection(
        ENVIRONMENT,
        string='Ambiente Destino',
        default='2',
        required=True)
    hr_software_id = fields.Char(string='NE Software ID')
    hr_software_pin = fields.Char(string='NE Software PIN')
    hr_test_set_id = fields.Char(string='Set Pruebas Id')

    antwort_gnr = fields.Text(string='Respuesta Rangos de Numeración')
    hr_provisions_pri = fields.Selection(
        [('no', 'No enviar'),
         ('monthly', 'Mensual'),
         ('consolidated', 'Consolidado')],
        'Provisiones Prima',
        default='no',
        help='No enviar: Se reportará en la nómina electrónica en el mes que se paga.\n'
            'Mensual: Se reportarán las provisiones mensualmente.\n'
            'Consolidado: Se reportará en la nomina electronica de diciembre la suma de todas las provisiones del año.')
    hr_provisions_ces = fields.Selection(
        [('no', 'No enviar'),
         ('monthly', 'Mensual'),
         ('consolidated', 'Consolidado')],
        'Provisiones Cesantías',
        default='no',
        help='No enviar: Se reportará en la nómina electrónica en el mes que se paga.\n'
            'Mensual: Se reportarán las provisiones mensualmente.\n'
            'Consolidado: Se reportará en la nomina electronica de diciembre la suma de todas las provisiones del año.')
    hr_provisions_vac = fields.Selection(
        [('no', 'No enviar'),
         ('monthly', 'Mensual'),
         ('consolidated', 'Consolidado')],
        'Provisiones Vacaciones',
        default='no',
        help='No enviar: Se reportará en la nómina electrónica en el mes que se paga.\n'
            'Mensual: Se reportarán las provisiones mensualmente.\n'
            'Consolidado: Se reportará en la nomina electronica de diciembre la suma de todas las provisiones del año.')

    def action_nie_GetNumberingRange(self):
        msg1 = _('Error desconocido,\nCódigo de estado: %s,\nRazón: %s.\n\n%s')
        msg2 = _('Error desconocido: %s\n.')
        wsdl = 'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl'
        s = 'http://www.w3.org/2003/05/soap-envelope'
        b = 'http://wcf.dian.colombia'

        GNR_werte = self._get_GNR_werte()
        GNR_werte['To'] = wsdl.replace('?wsdl', '')
        signiert_xml = satz.get_xml_soap_with_signature(
            satz.render_xml_edi(
                GNR_werte,
                'GetNumberingRange'
            ),
            GNR_werte['Id'],
            self.hr_certificate_file,
            self.hr_certificate_password
        )
        try:
            antwort = post(
                wsdl,
                headers={
                    'content-type': 'application/soap+xml;charset=utf-8'
                },
                data=etree.tostring(signiert_xml))

            if antwort.status_code == 200:
                root = etree.fromstring(antwort.text)
                antwort = ''

                for element in root.iter("{%s}Body" % s):
                    antwort = etree.tostring(element, pretty_print=True)
                    for element in root.iter("{%s}GetNumberingRangeResult" % b):
                        antwort = etree.tostring(element, pretty_print=True, encoding='utf-8')
                if antwort == '':
                    antwort = etree.tostring(root, pretty_print=True)

                self.write({'antwort_gnr': antwort})
            else:
                rtxt = ''
                if antwort.text:
                    rtxt = antwort.text.replace('><','>\n<')
                raise ValidationError(
                    msg1 % (antwort.status_code, antwort.reason, rtxt))

        except exceptions.RequestException as e:
            raise ValidationError(msg2 % (e))

        return True

    def _get_GNR_werte(self):
        xml_soap_werte = satz.get_xml_soap_values(self.hr_certificate_file,
                                                  self.hr_certificate_password)
        xml_soap_werte['accountCode'] = self.partner_id.vat
        xml_soap_werte['accountCodeT'] = self.partner_id.vat
        xml_soap_werte['softwareCode'] = self.hr_software_id
        return xml_soap_werte

    def verify_certificate_nie(self):
        self.ensure_one()
        try:
            _key, cert, _additional_certsout = satz.get_pkcs12(
                self.hr_certificate_file,
                self.hr_certificate_password
            )
            msg = _('The certificate file and password '
                    'were set correctly.\n\n\n %s', cert.subject.rfc4514_string())
            title = _('Success!')
            type_msg = 'success'
        except Exception as e:
            msg = '%s' % e
            title = _('Warning!')
            type_msg = 'danger'
        message = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': msg,
                'type': type_msg,
                'sticky': False,
            }
        }
        return message
