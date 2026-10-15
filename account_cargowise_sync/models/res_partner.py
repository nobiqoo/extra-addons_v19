# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    code_cw = fields.Char('Código CW')
    org_cw = fields.Char('Organización CW')
    salesman_code_cw = fields.Char('Código Vendedor CW')
    salesman_cw_id = fields.Many2one('res.partner', 'Vendedor CW')

    def create_partner_cargowise(self, vals):
        self = self.sudo().with_context(no_vat_validation=True)
        validated = self._validate_data_cw_create_partner(vals)
        p_type = validated.get('partner_type')
        vals_partner = {
            'company_type': (p_type == 'P' and 'person') or
                            (p_type == 'J' and 'company') or False,
            'name': validated['name'],
            'street': validated['street'],
            'city': validated['city'],
            'city_id': validated['city_id'],
            'state_id': validated['state'],
            'country_id': validated['country'],
            'l10n_latam_identification_type_id': validated['type_id'],
            'vat': validated['vat'],
            'phone': validated['phone'],
            'email': validated['email'],
            'code_cw': validated['id_partner'],
            'salesman_cw_id': validated['vendor'],
            'org_cw': validated['org_id'],
        }
        partner_id = self.create(vals_partner)
        return partner_id.id

    def _validate_data_cw_create_partner(self, vals):
        city_obj = self.env['res.city']
        state_obj = self.env['res.country.state']
        country_obj = self.env['res.country']
        type_id_obj = self.env['l10n_latam.identification.type']
        partner_obj = self.env['res.partner']
        city_id = False
        state_id = False
        country_id = False
        doc_type_id = False
        vendor_id = False
        msg_error = ''

        required_fields = {
            'partner_type': ('CNE001', 'Tipo de tercero'),
            'name': ('CNE002', 'Nombre del tercero'),
            'street': ('CNE003', 'Dirección'),
            'city': ('CNE004', 'Ciudad'),
            'state': ('CNE005', 'Departamento'),
            'country': ('CNE006', 'País'),
            'type_id': ('CNE007', 'Tipo de documento de identificación'),
            'vat': ('CNE008', 'Número de identificación'),
            'phone': ('CNE009', 'Teléfono'),
            'email': ('CNE010', 'Email'),
            'vendor': ('CNE011', 'Comercial'),
            'id_partner': ('CNE012', 'ID Tercero'),
            'org_id': ('CNE013', 'ID Organización'),
        }
        for fld, (code, name) in required_fields.items():
            if fld not in vals:
                msg_error += '\n- %s: Campo %s (%s) no se encuentra en la estructura XML.' % (
                    code, name, fld)

        if 'partner_type' in vals and not vals['partner_type']:
            msg_error += '\n- CV001: Campo Tipo de tercero (partner_type) es obligatorio.'
        if 'name' in vals and not vals['name']:
            msg_error += '\n- CV002: Campo Nombre del tercero (name) es obligatorio.'
        if 'street' in vals and not vals['street']:
            msg_error += '\n- CV003: Campo Dirección (street) es obligatorio.'
        if 'id_partner' in vals and not vals['id_partner']:
            msg_error += '\n- CV012: Campo ID Tercero (id_partner) es obligatorio.'

        if 'partner_type' in vals and vals.get('partner_type') not in ('P', 'J'):
            msg_error += '\n- NM001: Tipo de tercero "%s" no es válido (P o J).' % vals.get('partner_type')

        if vals.get('country'):
            country_id = country_obj.search_read(
                [('code', '=', vals['country'])], ['id', 'code'], limit=1)
            if not country_id:
                msg_error += '\n- NM002: No se encontró el País con código "%s".' % vals['country']

        if vals.get('state'):
            dom = []
            if country_id and country_id[0]['code'] == 'CO':
                dom.append(('country_id', '=', country_id[0]['id']))
            dom = ['|', ('code', '=', vals['state']), ('code_cw', '=', vals['state'])]
            state_id = state_obj.search_read(dom, ['id'], limit=1)
            if not state_id:
                msg_error += '\n- NM003: No se encontró el departamento con código "%s".' % vals['state']

        if state_id and country_id and country_id[0].get('code') == 'CO' and vals.get('city'):
            city_id = city_obj.search_read([
                ('active', '=', True),
                ('state_id', '=', state_id[0]['id']),
                ('country_id', '=', country_id[0]['id']),
                '|',
                ('dian_code', '=', vals['city']),
                ('name', 'ilike', vals['city']),
            ], ['id', 'name'], limit=1)

        if vals.get('type_id'):
            doc_type_id = type_id_obj.search_read(
                [('code_cw', '=', vals['type_id'])], ['id'], limit=1)
            if not doc_type_id:
                msg_error += '\n- NM004: No se encontró el Tipo de documento "%s".' % vals['type_id']

        if vals.get('vendor'):
            vendor_id = partner_obj.search_read(
                [('salesman_code_cw', '=', vals['vendor'])], ['id'], limit=1)
            if not vendor_id:
                msg_error += '\n- NM005: No se encontró el Vendedor con código "%s".' % vals['vendor']

        if vals.get('id_partner'):
            existing = partner_obj.search_read(
                [('code_cw', '=', vals['id_partner'])], ['id'])
            if existing:
                msg_error += '\n- TE001: Ya existe un tercero con ID CW: %s. IDs: %s.' % (
                    vals['id_partner'], [x['id'] for x in existing])

        if msg_error:
            raise ValidationError(_('%s') % msg_error)

        vat = vals.get('vat', '')
        if vat and '-' in vat:
            vat = vat.split('-')[0]

        return {
            'partner_type': vals.get('partner_type'),
            'name': vals.get('name'),
            'street': vals.get('street'),
            'city': vals.get('city'),
            'city_id': city_id and city_id[0]['id'] or False,
            'state': state_id and state_id[0]['id'] or False,
            'country': country_id and country_id[0]['id'] or False,
            'type_id': doc_type_id and doc_type_id[0]['id'] or False,
            'vat': vat,
            'phone': vals.get('phone'),
            'email': vals.get('email'),
            'vendor': vendor_id and vendor_id[0]['id'] or False,
            'id_partner': vals.get('id_partner'),
            'org_id': vals.get('org_id'),
        }
