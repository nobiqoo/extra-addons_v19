# -*- coding: utf-8 -*-

from lxml import etree
from requests import post, exceptions

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    ei_rndc_state = fields.Selection([('ok', 'Envío Exitoso'),
                                      ('or_error', 'Enviado con errores'),
                                      ('error', 'Envío Fallido'),
                                      ('other', 'Otro')],
                                    string='RNDC Estado',
                                    tracking=True)
    ei_rndc_response = fields.Text('Respuesta RNDC',
                                   tracking=True)
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#

    def button_rndc_senden(self):
        self.ensure_one()
        # datos {}
        data = self._get_invoice_rndc()
        # enviar al rndc
        response = self.rndc_senden(data)
        # procesar response
        ingreso_id = response.get('ingresoid', '')
        error = response.get('error', '')
        state = 'other'
        title = 'RNDC ESTADO DESCONOCIDO'
        msg = '%s\n%s' % (ingreso_id and 'Ingreso ID: %s' % ingreso_id,
                          error and 'Errores: %s' % error)
        type = 'warning'
        if ingreso_id and not error:
            state = 'ok'
            title = 'RNDC ENVIO EXITOSO'
            type = 'success'
        elif ingreso_id and error:
            state = 'ok_error'
            title = 'RNDC ENVIADO CON ERRORES'
            type = 'info'
        else:
            state = 'error'
            title = 'RNDC ENVÍO FALLIDO'
            type = 'danger'

        self.write({
            'ei_rndc_state': state,
            'ei_rndc_response': '\n'.join([title, msg])
        })
        # Retornar notificación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'type': type,
                'message': msg,
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    
    def rndc_datenantwort_erhalten(self, antwort):
        '''
           RNDC Antwort lesen
        '''
        daten = {}
        wurzel = etree.fromstring(antwort.text,)
        ns = wurzel.nsmap
        wurzel_body = wurzel.xpath('//SOAP-ENV:Body', namespaces=ns)
        if wurzel_body:
            ns = wurzel_body[0].nsmap
            wurzel_resp = wurzel[0].xpath('//NS1:AtenderMensajeRNDCResponse/return', namespaces=ns)
            if wurzel_resp:
                wurzel_resp = wurzel_resp[0]
                root = etree.fromstring(wurzel_resp.text.encode('ISO-8859-1'))
                errors = root.xpath('//ErrorMSG')
                ingreso_id = root.xpath('//ingresoid')
                daten['error'] = '\n'.join([element.text for element in errors])
                daten['ingresoid'] = ','.join([element.text for element in ingreso_id])

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
    
    def _decode_response(self, antwort):
        self.ensure_one()
        anfrageart = 'SendTestRNDC'
        exe_env, wsdl = self.company_id._rndc_zieldok_erhalten()
        if exe_env == '1':
            anfrageart = 'SendRNDC'
        
    
    def _get_invoice_rndc(self):
        self.ensure_one()
        if not self.fe_ad_file:
            raise ValidationError(
                _('El documento %s no tiene un archivo XML para enviar al RNDC',
                  self.name))
        company = self.company_id
        user, pwd = company._rndc_user_erhalten()
        return {
            'user': user, # 'FACTURACION@0512',
            'pwd': pwd, #'Global2024*', # PruebasRNDC
            'type': '1',
            'pid': '86',
            'nit_transport': ''.join([company.partner_id.vat,
                                      company.partner_id.l10n_co_verification_code or '']),
            'file_b64': self.fe_ad_file.decode('utf-8', 'ignore')
        }

    def rndc_senden(self, data):
        self.ensure_one()
        anfrageart = 'SendTestRNDC'
        exe_env, wsdl = self.company_id._rndc_zieldok_erhalten()
        if exe_env == '1':
            anfrageart = 'SendRNDC'
        anfrage = self._rdnc_anfrage(data)
        daten_antwort = False
        try:
            antwort = post(
                wsdl,
                headers={
                    'content-type': 'application/soap+xml;charset=utf-8'
                },
                data=anfrage
            )
            if antwort.status_code == 200:
                daten_antwort = self.rndc_datenantwort_erhalten(antwort)
                self.versandlog_erstellen(
                    anfrageart, daten_antwort, anfrage.decode(), exe_env)
            elif antwort.status_code in (500, 503, 507):
                # self.write({'state': 'fehler'})
                self.versandlog_erstellen(
                    anfrageart,
                    {
                        'status_code': antwort.status_code,
                        'reason': antwort.reason,
                        'response_text': antwort.text.replace('><', '>\n<'),
                    },
                    anfrage.decode(),
                    exe_env
                )
            else:
                raise ValidationError(
                    _('Error desconocido en metodo %s.\n'
                        'Contacte a su administrador.'
                        '\n\nCódigo estado: %s.\n Razón: %s',
                        anfrageart, antwort.status_code, antwort.reason))
        except exceptions.RequestException as e:
            raise ValidationError(
                _('Error desconocido en metodo %s.\n'
                  'Contacte a su administrador.'
                  '\n\n%s', anfrageart, e))
        return daten_antwort

    def _rdnc_anfrage(self, data={}):
        xml_content = self.env['ir.qweb']._render('l10n_co_bloodo_rndc.request_rndc', data)
        return b'<?xml version="1.0" encoding="utf-8"?>' + xml_content.encode()