# -*- coding: utf-8 -*-

from odoo import fields, models, api, _, tools
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fiscal_position_local = fields.Boolean(
        'Posición Fiscal Local',
        compute='_compute_fiscal_position_local',)

    dian_representation_type_id = fields.Many2one('dian.type_code',
                                        'Representación',
                                        help='Tipo de Representación',
                                        domain=[('type', '=', 'representation')])
    dian_establishment_type_id = fields.Many2one('dian.type_code',
                                        'Establecimiento',
                                        help='Tipo de establecimiento',
                                        domain=[('type', '=', 'establishment')])
    dian_obligation_type_ids = fields.Many2many('dian.type_code',
                                        'partner_dian_obligation_types',
                                        'partner_id', 'type_id',
                                        'Obligaciones y Responsabilidades',
                                        help='Obligaciones y Responsabilidades (FE)',
                                        domain=[('type', '=', 'obligation'),
                                                ('is_required_dian', '=', True)],
                                        tracking=True)
    dian_customs_type_ids = fields.Many2many('dian.type_code',
                                        'partner_dian_customs_types',
                                        'partner_id', 'type_id',
                                        'Usuario Aduanero',
                                        domain=[('type', '=', 'customs')])
    dian_fiscal_regimen = fields.Selection(
        [('48', 'Responsable del Impuesto sobre las ventas - IVA'),
         ('49', 'No responsables del IVA'),
         ('No aplica', 'No aplica')],
        'Regimen Fiscal',
        help='Regimen Fiscal (FE)',
        default='No aplica')
    dian_tax_scheme_id = fields.Many2one('dian.tax.type',
                                        'Responsabilidad fiscal',
                                        help='Responsabilidad fiscal (FE)',
                                        domain=[('dian_code', 'in', ('01', '04', 'ZA', 'ZZ'))],
                                        tracking=True)
    dian_commercial_name = fields.Char('Nombre comercial')

    # # vat_dv = fields.Char('DV', default='')
    l10n_co_verification_code = fields.Char('DV',
                                        compute='_compute_verification_code',
                                        help='Redundancy check to verify the vat number '
                                        'has been typed in correctly.',
                                        store=True)
    edi_email = fields.Char('Correo DIAN',
                            help='Correo para facturación electrónica.',
                            tracking=True)
    edi_email_cc = fields.Char('Correos copia DIAN',
                            help='Correos para enviar una copia de las '
                            'facturas electrónicas generadas a este tercero',
                            tracking=True)
    dian_not_send_email = fields.Boolean('No enviar correo DIAN',
                                        help='Marque esta casilla si no desea que se le envíen automaticamente correos relacionados con la facturación electrónica.',
                                        default=False,
                                        tracking=True)
    name1 = fields.Char('First name', tracking=True)
    name2 = fields.Char('Second name', tracking=True)
    lastname1 = fields.Char('Last name', tracking=True)
    lastname2 = fields.Char('Second last name', tracking=True)

    @api.depends_context('company')
    @api.depends('company_id')
    def _compute_fiscal_position_local(self):
        company = self.env.company
        for partner in self:
            if company and company.fiscal_position_local:
                partner.fiscal_position_local = True
            else:
                partner.fiscal_position_local = False

    @api.onchange('name1', 'name2', 'lastname1', 'lastname2')
    def _onchange_full_name(self):
        if self.company_type == 'person':
            name = (self.name1) if self.name1 else ''
            name = (name + ' ' + self.name2) if self.name2 else name
            name = (name + ' ' + self.lastname1) if self.lastname1 else name
            name = (name + ' ' + self.lastname2) if self.lastname2 else name
            self.name = name

    @api.depends('vat', 'l10n_latam_identification_type_id')
    def _compute_verification_code(self):
        multiplication_factors = [71, 67, 59, 53,
                                  47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]

        for partner in self:
            if partner.l10n_latam_identification_type_id.dian_code \
                    == '31':
                if partner.vat \
                    and partner.country_id == self.env.ref('base.co') \
                        and len(partner.vat) <= len(multiplication_factors):
                    number = 0
                    padded_vat = partner.vat

                    while len(padded_vat) < len(multiplication_factors):
                        padded_vat = '0' + padded_vat

                    # if there is a single non-integer in vat
                    # the verification code should be False
                    try:
                        for index, vat_number in enumerate(padded_vat):
                            number += int(vat_number) * \
                                multiplication_factors[index]

                        number %= 11

                        if number < 2:
                            partner.l10n_co_verification_code = number
                        else:
                            partner.l10n_co_verification_code = 11 - number
                    except ValueError:
                        partner.l10n_co_verification_code = False
                else:
                    partner.l10n_co_verification_code = False
            else:
                partner.l10n_co_verification_code = False

    def _get_verification_code(self, vat):
        multiplication_factors = [71, 67, 59, 53,
                                  47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3]
        dv = False
        if vat and len(vat) <= len(multiplication_factors):
            number = 0
            padded_vat = vat

            while len(padded_vat) < len(multiplication_factors):
                padded_vat = '0' + padded_vat

            # if there is a single non-integer in vat
            # the verification code should be False
            try:
                for index, vat_number in enumerate(padded_vat):
                    number += int(vat_number) * \
                        multiplication_factors[index]

                number %= 11

                if number < 2:
                    dv = number
                else:
                    dv = 11 - number
            except ValueError:
                dv = False
        return dv

    def _get_vat_without_verification_code(self):
        self.ensure_one()
        # last digit is the verification code
        # last digit is the verification code, but it could have a - before
        if self.l10n_latam_identification_type_id.l10n_co_document_code \
                != 'rut' or self.vat == '222222222222':
            return self.vat
        elif self.vat and '-' in self.vat:
            return self.vat.split('-')[0]
        return self.vat[:-1] if self.vat else ''

    def _get_vat_verification_code(self):
        self.ensure_one()
        if self.l10n_latam_identification_type_id.l10n_co_document_code \
                != 'rut':
            return ''
        elif self.vat and '-' in self.vat:
            return self.vat.split('-')[1]
        return self.vat[-1] if self.vat else ''

    def _get_fiscal_values(self):
        return self.dian_obligation_type_ids | \
            self.dian_customs_type_ids

    @api.constrains('vat', 'country_id')
    def _check_vat(self, validation="error"):
        if self.sudo().env.ref('base.module_base_vat').state == 'installed':
            self = self.filtered(
                lambda partner: partner.country_id != self.env.ref('base.co'))
            return super(ResPartner, self)._check_vat(validation=validation)
        else:
            return True
    
    @api.model
    def find_or_create(self, email, assert_valid_email=False):
        """ Override to use the email_normalized field. """
        if not email:
            raise ValueError(_('An email is required for find_or_create to work'))

        parsed_name, parsed_email_normalized = tools.parse_contact_from_email(email)
        if not parsed_email_normalized and assert_valid_email:
            raise ValueError(_('%(email)s is not recognized as a valid email. This is required to create a new customer.'))
        if parsed_email_normalized:
            domain = [('email_normalized', '=', parsed_email_normalized)]
            if self.env.company:
                domain.append(('company_id', 'in', [self.env.company.id, False]))
            partners = self.search(domain, limit=1)
            if partners:
                return partners

        # We don't want to call `super()` to avoid searching twice on the email
        # Especially when the search `email =ilike` cannot be as efficient as
        # a search on email_normalized with a btree index
        # If you want to override `find_or_create()` your module should depend on `mail`
        create_values = {self._rec_name: parsed_name or parsed_email_normalized}
        if parsed_email_normalized:  # otherwise keep default_email in context
            create_values['email'] = parsed_email_normalized
        return self.create(create_values)

    
    @api.constrains('vat', 'company_id', 'commercial_partner_id')
    def _check_document_number_unique(self):
        enable_check = self.env.company.duplicate_contacts
        if not enable_check:
            for record in self:
                if record.vat == '222222222222':
                    continue
                if record.vat:
                    duplicated_partners = self.search([
                        ('vat', '=', record.vat),
                        ('commercial_partner_id.id', '!=', record.commercial_partner_id.id),
                        '|',
                        ('company_id', '=', self.env.company.id),
                        ('company_id', '=', False)
                    ])
                    if duplicated_partners:
                        raise ValidationError(
                            _("El número de documento %s ya está siendo utilizado " \
                              "por otro contacto.\nPartners: \n%s", 
                              record.vat, '\n'.join(
                                  ['>>> [id#%s] %s | Compañía: %s' % (x.id, x.name, x.company_id.name)
                                   for x in duplicated_partners])))
