# -*- coding: utf-8 -*-

import traceback

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # @api.model
    # def create(self, vals):
    #     res = super(ResPartner, self).create(vals)
    #     # if res.edi_email:
    #     #     res._get_contact_edi_email(False, res.edi_email)
    #     return res
    
    # def write(self, vals):
    #     # for record in self:
    #         # old_edi_email = record.edi_email or False
    #         # new_edi_email = vals.get('edi_email', False)
    #         # if old_edi_email != new_edi_email:
    #         #     if 'edi_email' in vals and not new_edi_email:
    #         #         new_edi_email = 'delete'
    #         #     record._get_contact_edi_email(old_edi_email, new_edi_email)
    #     res = super(ResPartner, self).write(vals)
    #     return res
    
    def _get_contact_edi_email(self, old_edi_email='', new_edi_email=''):
        '''
        Crear contacto con correo de factura electrónica.
        '''
        partner_obj = self.env['res.partner']
        for partner in self:
            partner_id = False
            if old_edi_email:
                partner_id = partner_obj.search([
                    ('parent_id','=',partner.id),
                    ('email','=',old_edi_email),
                    ('name','=',partner.name + _(' - Correo Factura Electrónica')),
                    ('type','=','invoice'),
                ])
            if partner_id:
                if new_edi_email and new_edi_email != 'delete':
                    partner_id.write({
                        'email': new_edi_email,
                        'active': True
                    })
                elif new_edi_email == 'delete':
                    partner_id.write({
                        'active': False
                    })
                else: pass
            else:
                if new_edi_email:
                    partner_id = partner_obj.search([
                        ('parent_id','=',partner.id),
                        ('email','=',new_edi_email),
                        ('name','=',partner.name + _(' - Correo Factura Electrónica')),
                        ('type','=','invoice'),
                        ('active','=',False)
                    ])
                    if partner_id:
                        partner_id.write({
                            'active': True
                        })
                    else:
                        partner_obj.create({
                            'name': partner.name + _(' - Correo Factura Electrónica'),
                            'email': new_edi_email,
                            'type': 'invoice',
                            'parent_id': partner.id
                        })
                else:
                    partner_obj.create({
                        'name': partner.name + _(' - Correo Factura Electrónica'),
                        'email': old_edi_email,
                        'type': 'invoice',
                        'parent_id': partner.id
                    })
                    # pass

    def _get_dian_code_for_identification_type(self, partner):
        IDENTIFICATION_TYPE_TO_DIAN_CODE = {
            'rut': '31',
            'id_card': '12',
            'national_citizen_id': '13',
            'id_document': '12',
            'passport': '41',
            'external_id': '21',
            'foreign_id_card': '22',
            'diplomatic_card': 'O-99',
            'residence_document': 'O-99',
            'civil_registration': '11',
        }

        identification_type = \
            partner.l10n_latam_identification_type_id.l10n_co_document_code
        return IDENTIFICATION_TYPE_TO_DIAN_CODE[
            identification_type] if identification_type else ''

    def _get_partner_dian_type(self):
        self.ensure_one()
        if self.is_company:
            return '1'
        else:
            return '2'

    def _get_address_partner_edi(self):
        if self.country_id:
            if self.country_id.code == 'CO':
                if not self.city_id:
                    raise UserError(
                        _('%s no tiene una ciudad establecida.', self.name))
                elif not self.state_id:
                    raise UserError(
                        _('%s no tiene un departmento establecido.', self.name))
        else:
            raise UserError(
                _('%s no tiene un país establecido.', self.name))
        return {
            'AddressID': self.city_id.dian_code or '',
            'AddressCityName': self.city_id \
                and self.city_id.name \
                    or self.city or '',
            'AddressPostalZone': self.zip \
                or self.city_id.zipcode \
                    or self.city_id.dian_code or '',
            'AddressCountrySubentity': self.state_id.name or '',
            'AddressCountrySubentityCode': self.state_id \
                and self.state_id.dian_code or '',
            'AddressLine': self.street or '',
            'CountryIdCode': self.country_id.code,
            'CountryName': self.country_id.name
        }

    def _personendetails_erhalten(self):
        self.ensure_one()
        msg = ''
        person_type = self._get_partner_dian_type()

        # Ubicaciones
        if self.country_id:
            if self.country_id.code == 'CO' and not self.city_id:
                msg += _('\n- No tiene la ciudad.')
            if self.country_id.code == 'CO' and not self.state_id:
                msg += _('\n- No tiene el departamento.')
        else:
            msg += _('\n- No tiene el país.')

        # Identificación
        id_type_id = self.l10n_latam_identification_type_id
        if id_type_id:
            document_type_code = id_type_id.dian_code
            if not document_type_code:
                msg += _('\n- Tipo de documento [%s] no tiene código DIAN.',
                         id_type_id.name)
            if document_type_code == '31' \
                    and not self.l10n_co_verification_code:
                msg += _('\n- No tiene dígito de verificación.')
            if not self.vat:
                msg += _('\n- No tiene número de identificación.')
        else:
            msg += _('\n- No tiene documento de identificación.')

        if not (self.dian_obligation_type_ids \
                or self.property_account_position_id.dian_obligation_type_ids):
            msg += _('\n- No tiene el tipo de obligación fiscal.')
        if not (self.dian_tax_scheme_id \
                or self.property_account_position_id.dian_tax_scheme_id):
            msg += _('\n- No tiene la responsabilidad fiscal.')
        if msg:
            raise ValidationError(
                _('Error extrayendo datos del tercero: %s'
                  '\n%s\n\nPor favor, configurelo desde Contactos.',
                  self.name, msg))
        dian_ob_type_ids = self.dian_obligation_type_ids \
            or self.property_account_position_id.dian_obligation_type_ids
        tax_level_codes = ';'.join(
            [t.dian_code for t in dian_ob_type_ids]
        )
        tax_scheme_id = self.dian_tax_scheme_id \
            and self.dian_tax_scheme_id \
                or self.property_account_position_id \
                    and self.property_account_position_id.dian_tax_scheme_id

        telephone = False
        if self.phone:
            telephone = self.phone

        return {
            'AdditionalAccountID': person_type,
            'PartyName': self.dian_commercial_name or self.name or '',
            'Name': self.name,
            'AddressID': self.city_id.dian_code or '',
            'AddressCityName':  self.city_id \
                and self.city_id.name \
                    or self.city or '',
            'AddressPostalZone': self.zip \
                or self.city_id.zipcode \
                    or self.city_id.dian_code or '',
            'AddressCountrySubentity': self.state_id \
                and self.state_id.name or '',
            'AddressCountrySubentityCode': self.state_id \
                and self.state_id.dian_code or '',
            'AddressLine': self.street or '',
            'CompanyIDschemeID': self.l10n_co_verification_code,
            'CompanyIDschemeName': id_type_id \
                and id_type_id.dian_code,
            'CompanyID': self.vat,
            'listName': 'No aplica',  # self.dian_fiscal_regimen,
            'TaxLevelCode': tax_level_codes,
            'TaxSchemeID': tax_scheme_id.dian_code,
            'TaxSchemeName': tax_scheme_id.name,
            'CorporateRegistrationSchemeName': self.ref,
            'CountryIdCode': self.country_id.code,
            'CountryName': self.country_id.name,
            'Telephone': telephone,
            'Telefax': '',
            'ElectronicMail': self.edi_email or self.email,
        }

    def _get_TaxRepresentativeParty(self, force_raise=False):
        id_type_id = self.l10n_latam_identification_type_id
        error_msg = ''
        if not id_type_id:
            error_msg += _('%s no tiene tipo de identificación.\n', self.name)
        if not self.vat:
            error_msg += _('%s no tiene número de identificación.\n', self.name)
        if not self.l10n_co_verification_code \
                and id_type_id.dian_code == '31':
            error_msg += _('%s no tiene dígito de verificación.\n', self.name)
        if error_msg and force_raise:
            raise ValidationError(
                _('Error extrayendo datos del contacto: %s'
                  '\n%s\nPor favor, configurelo desde Contactos.',
                  self.name, error_msg))
        if error_msg:
            return error_msg, False
        return '', {
            'ID': self.vat,
            'IDschemeID': self.l10n_co_verification_code,
            'IDschemeName': id_type_id.dian_code,
        }

    def _ar_personendetails_erhalten(self):
        self.ensure_one()
        msg = ''
        person_type = self._get_partner_dian_type()

        # Identificación
        id_type_id = self.l10n_latam_identification_type_id
        if id_type_id:
            document_type_code = id_type_id.dian_code
            if not document_type_code:
                msg += _('\n- Tipo de documento [%s] no tiene código DIAN.',
                         id_type_id.name)
            if document_type_code == '31' \
                    and not self.l10n_co_verification_code:
                msg += _('\n- No tiene dígito de verificación.')
            if not self.vat:
                msg += _('\n- No tiene número de identificación.')
        else:
            msg += _('\n- No tiene documento de identificaxión.')

        if not (self.dian_tax_scheme_id \
                or self.property_account_position_id.dian_tax_scheme_id):
            msg += _('\n- No tiene la responsabilidad fiscal.')
        if msg:
            raise ValidationError(
                _('Error extrayendo datos del tercero:  %s'
                  '\n%s\nPor favor, configurelo desde Contactos.',
                  self.name, msg))
        dian_ob_type_ids = self.dian_obligation_type_ids \
            or self.property_account_position_id.dian_obligation_type_ids
        tax_level_codes = ';'.join(
            [t.dian_code for t in dian_ob_type_ids]
        )
        tax_scheme_id = self.dian_tax_scheme_id \
            and self.dian_tax_scheme_id \
                or self.property_account_position_id \
                    and self.property_account_position_id.dian_tax_scheme_id

        return {
            'RegistrationName': self.name,
            'CompanyID': self.vat,
            'schemeID': self.l10n_co_verification_code,
            'schemeName': id_type_id and id_type_id.dian_code,
            'AdditionalAccountID': person_type,
            'TaxSchemeID': tax_scheme_id.dian_code,
            'TaxSchemeName': tax_scheme_id.name,
            'TaxLevelCode': tax_level_codes,
        }

    def _ar_person_erhalten(self):
        self.ensure_one()
        msg = ''

        # Identificación
        id_type_id = self.l10n_latam_identification_type_id
        if id_type_id:
            document_type_code = id_type_id.dian_code
            if not document_type_code:
                msg += _('\n- Tipo de documento [%s] no tiene código DIAN.',
                          id_type_id.name)
            if document_type_code == '31' \
                    and not self.l10n_co_verification_code:
                msg += _('\n- No tiene dígito de verificación.')
            if not self.vat:
                msg += _('\n- No tiene número de identificación.')
        else:
            msg += _('\n- No tiene documento de identificaxión.')
        if msg:
            raise ValidationError(
                _('Error extrayendo datos del tercero:  %s'
                  '\n%s\nPor favor, configurelo desde Contactos.',
                  self.name, msg))
        names = self._name_nachname_erhalten()
        return {
            'ID': self.vat,
            'schemeID': self.l10n_co_verification_code,
            'schemeName': id_type_id and id_type_id.dian_code,
            'FirstName': names.get('name', '-'),
            'FamilyName': names.get('nachname', '-'),
            'JobTitle': 'Desconocido',
            'OrgDep': 'Desconocido'
        }

    def _name_nachname_erhalten(self):
        self.ensure_one()
        if self.name1 and self.lastname1:
            name = '%s %s' % (self.name1,
                              self.name2 or '')
            nachname = '%s %s' % (self.lastname1,
                                  self.lastname2 or '')
        else:
            base_name = self.name.split()
            if len(base_name) == 1:
                name = base_name[0]
                nachname = base_name[0]
            elif len(base_name) >= 2:
                name = base_name[0]
                nachname = base_name[-1]
            else:
                name = 'Desconocido'
                nachname = 'Desconocido'
        return {
            'name': name.strip(),
            'nachname': nachname.strip()
        }
