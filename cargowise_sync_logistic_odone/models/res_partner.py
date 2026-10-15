# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    code_cw = fields.Char('Código CW')
    org_cw = fields.Char('Organización CW')
    salesman_code_cw = fields.Char('Código Vendedor CW')
    salesman_cw_id = fields.Many2one('res.partner', 'Vendedor CW')

    def create_partner_cargowise(self, vals):
        # log
        log_ok = self.env['ir.config_parameter'].sudo().get_param('cargowise.sync.logistic.log')
        if log_ok:
            _logger.info('\n--------- LOGISTIC ---------')
            _logger.info(vals)
            _logger.info('\n----------------------------')
        # Resolver compañía (opcional)
        company_id = False
        if vals.get('company_code'):
            company_id = self._resolve_partner_company_cw(vals['company_code'])

        if company_id:
            self = self.with_company(company_id).with_context(no_vat_validation=True)
        else:
            self = self.with_context(no_vat_validation=True)

        validated = self._validate_data_cw_create_partner(vals, company_id)
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
            'property_payment_term_id': validated['payment_term_id'],
        }
        # Asignar compañía solo si se especificó
        if company_id:
            vals_partner['company_id'] = company_id
        partner_id = self.create(vals_partner)
        return partner_id.id

    def _resolve_partner_company_cw(self, company_code):
        """Resuelve la compañía para creación de contactos.
        Busca por el código CargoWise de la compañía (cw_code)."""
        company = self.env['res.company'].search(
            [('cw_code', '=', company_code)], limit=1)
        if not company:
            raise ValidationError(_(
                'No se encontró la compañía con código "%s". '
                'Verifique el campo company_code.'
            ) % company_code)
        return company.id

    def _validate_data_cw_create_partner(self, vals, company_id=False):
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
        # Campo no está en xml
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

        # Campo vacío
        if 'partner_type' in vals and not vals['partner_type']:
            msg_error += '\n- CV001: Campo Tipo de tercero (partner_type) es obligatorio.'
        if 'name' in vals and not vals['name']:
            msg_error += '\n- CV002: Campo Nombre del tercero (name) es obligatorio.'
        if 'street' in vals and not vals['street']:
            msg_error += '\n- CV003: Campo Dirección (street) es obligatorio.'
        if 'city' in vals and not vals['city']:
            msg_error += '\n- CV004: Campo Ciudad (city) es obligatorio.'
        if 'state' in vals and not vals['state']:
            msg_error += '\n- CV005: Campo Departamento (state) es obligatorio.'
        if 'country' in vals and not vals['country']:
            msg_error += '\n- CV006: Campo País (country) es obligatorio.'
        if 'type_id' in vals and not vals['type_id']:
            msg_error += '\n- CV007: Campo Tipo de documento de identificación (type_id) es obligatorio.'
        if 'vat' in vals and not vals['vat']:
            msg_error += '\n- CV008: Campo Número de identificación (vat) es obligatorio.'
        if 'phone' in vals and not vals['phone']:
            pass
            # msg_error += '\n- CV009: Campo Teléfono (phone) es obligatorio.'
        if 'email' in vals and not vals['email']:
            msg_error += '\n- CV010: Campo Email (email) es obligatorio.'
        if 'vendor' in vals and not vals['vendor']:
            pass
            # msg_error += '\n- CV011: Campo Comercial (vendor) es obligatorio.'
        if 'id_partner' in vals and not vals['id_partner']:
            msg_error += '\n- CV012: Campo ID Tercero (id_partner) es obligatorio.'
        if 'org_id' in vals and not vals['org_id']:
            msg_error += '\n- CV013: Campo ID Organización (org_id) es obligatorio.'

        # Mapeos
        if 'partner_type' in vals and vals['partner_type'] not in ('P', 'J'):
            msg_error += '\n- NM001: Tipo de tercero "%s" no es válido (P: Persona natural, J: Compañia).' % vals.get('partner_type')

        if vals.get('country'):
            country_id = country_obj.search_read(
                [('code', '=', vals['country'])], ['id', 'code'], limit=1)
            if not country_id:
                msg_error += '\n- NM002: No se encontró el País con código "%s".' % vals['country']

        if vals.get('state'):
            dom = [('code', '=', vals['state'])]
            if country_id and country_id[0]['code'] == 'CO':
                dom.append(('country_id', '=', country_id[0]['id']))
            state_id = state_obj.search_read(dom, ['id'], limit=1)
            if not state_id:
                msg_error += '\n- NM003: No se encontró el departamento con código "%s".' % vals['state']

        if state_id and country_id and country_id[0]['code'] == 'CO' and vals.get('city'):
            city_id = city_obj.search_read([
                ('active', '=', True),
                ('state_id', '=', state_id[0]['id']),
                ('country_id', '=', country_id[0]['id']),
                '|',
                ('dian_code', '=', vals['city']),
                ('name', 'ilike', vals['city']),
            ], ['id', 'name', 'dian_code'], limit=1)

        if vals.get('type_id'):
            doc_type_id = type_id_obj.search_read(
                [('code_cw', '=', vals['type_id'])], ['id'], limit=1)
            if not doc_type_id:
                msg_error += '\n- NM004: No se encontró el Tipo de documento de identificación con código "%s".' % vals['type_id']

        if vals.get('vendor'):
            vendor_domain = [('salesman_code_cw', '=', vals['vendor'])]
            if company_id:
                vendor_domain.append(
                    ('company_id', 'in', [company_id, False]))
            vendor_id = partner_obj.search_read(
                vendor_domain, ['id'], limit=1)
            if not vendor_id:
                msg_error += '\n- NM005: No se encontró el Vendedor con código "%s".' % vals['vendor']

        pterm_id = False
        if 'payment_term' in vals and vals['payment_term']:
            pterms = self.env['account.payment.term'].search([])
            term = vals.get('payment_term', False)
            if isinstance(term, int):
                pass
            elif isinstance(term, str) and term.isdigit():
                term = int(term)
            else:
                msg_error += '\n- NM006: El valor recibido para el término de pago (payment_term) no es un número entero.'
            pterm_id = pterms.filtered(lambda p: sum(p.line_ids.mapped('nb_days')) == term)
            if not pterm_id:
                msg_error += '\n- NM007: No se encontró el término de pago con valor "%s" (Campo "payment_term") en la BD de Odoo.' % vals['payment_term']

        # Tercero existente
        if vals.get('id_partner'):
            partner_domain = [
                ('code_cw', '!=', False),
                ('code_cw', '=', vals['id_partner'])
            ]
            if company_id:
                partner_domain.append(
                    ('company_id', 'in', [company_id, False]))
            partners = partner_obj.search_read(partner_domain, ['id'])
            if partners:
                msg_error += '\n- TE001: Ya existe un tercero con ID: %s (id_partner), Registros existentes: %s.' % (
                    vals['id_partner'], [x['id'] for x in partners])

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
            'payment_term_id': pterm_id and pterm_id[0].id or False,
        }
