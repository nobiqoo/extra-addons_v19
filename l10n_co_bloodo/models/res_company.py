# -*- coding: utf-8 -*-

from . import ir_sentences as satz
from requests import post, exceptions
from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    type_einvoicing = fields.Selection([('no', 'No Aplica'),
                                        ('edi_dir', 'Directa a la DIAN'),],
                                       'Facturación electrónica',
                                       default='no')

    fv_sent = fields.Integer('fv enviados')
    nc_sent = fields.Integer('nc enviados')
    nd_sent = fields.Integer('nd enviados')
    zip_sent = fields.Integer('Zips enviados')
    ar_sent = fields.Integer('ar enviados')
    ad_sent = fields.Integer('ad enviados')
    ds_sent = fields.Integer('ds enviados')
    nas_sent = fields.Integer('nas enviados')
    ars_sent = fields.Integer('ars enviados')

    target_environment_id = fields.Selection([('1', 'Producción'),
                                              ('2', 'Test')],
                                             'Ambiente de destino',
                                             default='2',
                                             required=True)
    test_set_id = fields.Char('Test Set Id')
    software_id = fields.Char('Software Id')
    software_pin = fields.Char('Software PIN')
    certificate_filename = fields.Char('Nombre certificado')
    certificate_file = fields.Binary('Certificado')
    certificate_password = fields.Char('Pwd certificado')
    signature_policy_url = fields.Char('Url signature policy',
        default='https://facturaelectronica.dian.gov.co'
                '/politicadefirma/v2/politicadefirmav2.pdf')
    signature_policy_description = fields.Char('Signature policy description',
        default='Política de firma para facturas '
        'electrónicas de la República de Colombia.')
    signature_policy_filename = fields.Char('Signature policy file name')
    signature_policy_file = fields.Binary('Signature policy file')
    sign_url = fields.Char('Sign url', default='')
    response_get_numbering_range = fields.Text('Response of numbering ranges')
    tributary_information = fields.Text('Información Tributaria')

    edi_email = fields.Char('Correos FE',
                            help='Correo de origen para '
                            'facturación electrónica')
    edi_email_error = fields.Char('Correos para errores',
                            help='Para agregar varios correos, '
                            'se debe separar con una coma (,).')
    report_template = fields.Many2one('ir.actions.report',
                                      'Formato para FE')
    report_template_nc = fields.Many2one('ir.actions.report',
                                      'Formato para NC')
    report_template_exp = fields.Many2one('ir.actions.report',
                                      'Formato para FE Exportación')
    fname_pdf_same_xml = fields.Boolean('Mismo nombre para PDF y XML',
        help='Al activar esta opción, el archivo PDF generado tendrá el mismo nombre que el XML de la factura electrónica.')
    email_attach_doc = fields.Boolean('Adjuntos doc en correo',
                            help='Agregar al correo de factura electrónica'
                            ' los archivos adjuntos en la factura',
                            default=False)
    # DS
    type_support_doc = fields.Selection([('no', 'No Aplica'),
                                         ('edi_dir', 'Directo a la DIAN'), ],
                                        'Documento soporte',
                                        default='no')
    ds_target_environment_id = fields.Selection([('1', 'Producción'),
                                                 ('2', 'Prueba')],
                                                'Ambiente de destino (DS)',
                                                default='2',
                                                required=True)

    ds_test_set_id = fields.Char('SD Test Set Id')
    ds_software_id = fields.Char('SD Software Id')
    ds_software_pin = fields.Char('SD Software PIN')

    ei_fiscal_respo = fields.Char('Responabilidad fiscal',
        help='Texto de responsabilidad fiscal que se presenta en el '
        'encabezado del formato de factura electronica')
    
    fe_send_later = fields.Boolean('Enviar después',
                                help='La factura electrónica será enviada '
                                'posteriormente a través de un proceso en segundo plano '
                                'que se ejecuta cada 15 minutos.',
                                default=False,
                                tracking=True)

    def write(self, vals):
        res = super(ResCompany, self).write(vals)
        for record in self:
            if vals.get('edi_email'):
                record.partner_id.write({
                    'edi_email': record.edi_email
                })
        return res

    def action_GetNumberingRange(self):
        msg1 = _('Error desconocido,\nCódigo de estado: %s,\nRazón: %s.\n\n%s')
        msg2 = _('Error desconocido: %s\n.')
        wsdl = 'https://vpfe.dian.gov.co/WcfDianCustomerServices.svc?wsdl'
        s = 'http://www.w3.org/2003/05/soap-envelope'
        b = 'http://wcf.dian.colombia'

        GetNumberingRange_values = self._get_GetNumberingRange_values()
        GetNumberingRange_values['To'] = wsdl.replace('?wsdl', '')
        xml_soap_with_signature = satz.get_xml_soap_with_signature(
            satz.render_xml_edi(
                GetNumberingRange_values,
                'GetNumberingRange'
            ),
            GetNumberingRange_values['Id'],
            self.certificate_file,
            self.certificate_password
        )
        try:
            response = post(
                wsdl,
                headers={
                    'content-type': 'application/soap+xml;charset=utf-8'
                },
                data=etree.tostring(xml_soap_with_signature))

            if response.status_code == 200:
                root = etree.fromstring(response.text)
                response = ''

                for element in root.iter('{%s}Body' % s):
                    response = etree.tostring(element, pretty_print=True)
                    for element in root.iter(
                            '{%s}GetNumberingRangeResult' % b):
                        response = etree.tostring(
                            element, pretty_print=True, encoding='utf-8')
                if response == '':
                    response = etree.tostring(root, pretty_print=True)

                self.write({'response_get_numbering_range': response})
            else:
                rtxt = ''
                if response.text:
                    rtxt = response.text.replace('><','>\n<')
                raise ValidationError(
                    msg1 % (response.status_code, response.reason, rtxt))

        except exceptions.RequestException as e:
            raise ValidationError(msg2 % (e))

        return True

    def _get_GetNumberingRange_values(self):
        xml_soap_values = satz.get_xml_soap_values(self.certificate_file,
                                                   self.certificate_password)
        xml_soap_values['accountCode'] = self.partner_id.vat
        xml_soap_values['accountCodeT'] = self.partner_id.vat
        xml_soap_values['softwareCode'] = self.software_id
        return xml_soap_values

    def verify_certificate(self):
        self.ensure_one()
        try:
            _key, cert, _additional_certsout = satz.get_pkcs12(
                self.certificate_file,
                self.certificate_password
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
    
    def action_xml_by_key(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consultar XML'),
            'view_mode': 'form',
            'res_model': 'xml.by.document.key',
            'target': 'new',
            'context': {
                'default_company_id': self.id
            },
        }
    
    def _get_or_create_sequence_dian_sent(self, code, field=None):
        sequence = self.env['ir.sequence'].search([
            ('code', '=', code),
            ('company_id', '=', self.id)
        ], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].create({
                'name': 'DIAN %s Sent - %s' % (code.upper(), self.name),
                'code': code,
                'company_id': self.id,
                'implementation': 'standard',
                'use_date_range': False,
                'number_increment': 1,
                'padding': 0,
                'number_next_actual': getattr(self, field) + 1 if field else 1,
                'prefix': '',
                'suffix': '',
            })
        return sequence
