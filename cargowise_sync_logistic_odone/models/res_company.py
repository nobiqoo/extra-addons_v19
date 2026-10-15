# -*- coding: utf-8 -*-
from base64 import b64encode
from requests import post

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    api_cw_server = fields.Char(
        'Servidor CW',
        default='TRN',
        help='PRD: Producción, TRN: Test',
    )
    api_cw_url = fields.Char(
        'URL CW',
        default='https://c07trnservices.wisegrid.net/eAdaptor',
    )
    api_cw_pass = fields.Char('Contraseña CW', default='PRUEBAS')
    api_cw_user = fields.Char('Usuario CW', default='PRUEBAS')
    api_cw_enterprise_id = fields.Char('EnterpriseID', default='C07')
    api_cw_event_type = fields.Char('EventType', default='DIM')
    api_cw_event_reference = fields.Char('EventReference', default='DIM')
    cw_code = fields.Char('Código CW',
        help='Código de la compañía usado por CargoWise para '
        'identificar en qué compañía crear facturas y contactos.'
    )

    def _get_authorization_cw_api(self):
        self.ensure_one()
        if not self.api_cw_user or not self.api_cw_pass:
            raise ValidationError(_(
                'Usuario o contraseña incompletos para la conexión con CargoWise.'
            ))
        auth = '%s:%s' % (self.api_cw_user, self.api_cw_pass)
        return b64encode(auth.encode()).decode()

    def test_conection_cw(self):
        self.ensure_one()
        xml = '<UniversalEvent xmlns="http://www.cargowise.com/Schemas/Universal/2011/11"></UniversalEvent>'
        url = self.api_cw_url
        header = {'Authorization': 'Basic %s' % self._get_authorization_cw_api()}
        response = post(url=url, headers=header, data=xml.encode('utf-8'))
        raise ValidationError(
            'Respuesta Api CW:\nEstado: %s\n%s' % (
                response.status_code, response.text))
