# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    rndc_env_id = fields.Selection([('1', 'Producción'),
                                    ('2', 'Pruebas')],
                                   string='Ambiente RNDC',
                                   default='2')
    rndc_wsdl = fields.Char('RNDC WSDL',
        default="http://rndcws.mintransporte.gov.co:8080/soap/IBPMServices")
    rndc_wsdl2 = fields.Char('RNDC WSDL CONTINGENCIA',
        default="http://rndcws2.mintransporte.gov.co:8080/soap/IBPMServices")
    rndc_wsdl_test = fields.Char('RNDC WSDL TEST',
        default="http://plc.mintransporte.gov.co:8080/soap/IBPMServices")
    rndc_use_wsdl2 = fields.Boolean('Contigencia',
                                    default=False)
    rndc_user = fields.Char('RNDC Usuario')
    rndc_pwd = fields.Char('RNDC Clave')
    rndc_pwd_test = fields.Char('RNDC Clave Test')
    
    def _rndc_zieldok_erhalten(self):
        self.ensure_one()
        wsdl = self.rndc_wsdl_test
        if self.rndc_env_id == '1':
            wsdl = self.rndc_wsdl
            if self.rndc_use_wsdl2:
                wsdl = self.rndc_wsdl2
        return self.rndc_env_id, wsdl
    
    def _rndc_user_erhalten(self):
        user = self.env.user.rndc_user  \
            or self.rndc_user or ''
        if self.rndc_env_id == '2':
            pwd = self.rndc_pwd_test or ''
        else:
            pwd = self.env.user.rndc_pwd or self.rndc_pwd or ''
        return user, pwd