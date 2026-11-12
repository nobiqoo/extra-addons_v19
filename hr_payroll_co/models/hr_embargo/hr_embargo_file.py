# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.utilities_collection import string

BREAK_LINE = '\r\n'

# Colombian localizations mark NIT with DIAN document-type code '31'; anything
# else is treated as Cédula for the purposes of this file (the Banco Agrario
# design only defines these two types for the fields below).
NIT_DIAN_CODE = '31'


class HrEmbargoFile(models.Model):
    _name = 'hr.embargo.file'
    _description = 'Judicial Deposit Flat File'
    _order = 'id desc'

    name = fields.Char(string='Name', readonly=True)
    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    cc = fields.Char(
        string='CC', required=True, default=lambda self: self._default_cc(),
        help='Two-digit daily sequence used to tell apart several files generated the same '
             'day (part of the file name: GDYYYYMMDDXXXXXXXXXXX_CC.TXT).')
    origin_office = fields.Char(
        string='Origin Office (SBAN)', default='0030',
        help='Bank office code. Use 0030 for account-debit payments (Recepción Medio de Pago '
             'en Línea); use the paying office\'s code for PIN/in-branch payments.')
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    line_ids = fields.One2many(
        comodel_name='hr.embargo.file.line', inverse_name='file_id', string='Lines')
    file_data = fields.Binary(string='File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)

    def _default_cc(self):
        today = fields.Date.context_today(self)
        count = self.search_count([
            ('create_date', '>=', f'{today} 00:00:00'),
            ('create_date', '<=', f'{today} 23:59:59'),
            ('company_id', '=', self.env.company.id),
        ])
        return str(count + 1).zfill(2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('seq.hr.embargo.file') or ''
        return super(HrEmbargoFile, self).create(vals_list)

    def action_load_lines(self):
        for record in self:
            record.line_ids.unlink()
            embargo_lines = self.env['hr.embargo.line'].search([
                ('state', '=', 'paid'),
                ('period_id.start', '>=', record.date_start),
                ('period_id.start', '<=', record.date_end),
                ('embargo_id.company_id', '=', record.company_id.id),
            ])
            record.line_ids = [(0, 0, {'embargo_line_id': line.id}) for line in embargo_lines]

    def _get_document_type_code(self, partner):
        if not partner or not partner.l10n_latam_identification_type_id:
            return '1'
        return '3' if partner.l10n_latam_identification_type_id.dian_code == NIT_DIAN_CODE else '1'

    def _get_lastname_firstname(self, partner):
        if not partner:
            return '', ''
        if partner.is_company:
            return string.unicode_remove_accents(partner.name or ''), ''
        return (
            string.unicode_remove_accents(partner.lastname1 or ''),
            string.unicode_remove_accents(partner.name1 or ''),
        )

    def _build_control_record(self):
        self.ensure_one()
        partner = self.company_id.partner_id
        is_nit = self._get_document_type_code(partner) == '3'
        # Field 6 ("Identificación de la entidad") is only 10 positions wide in
        # the source design, unlike the 11-digit consignor id used in the file
        # name — appending the NIT verification digit here could overflow and
        # get silently truncated, so it is deliberately left out. Verify this
        # against the original Banco Agrario spec before using in production
        # (see the ambiguity flagged when this file generator was built).
        lastname, unused_firstname = self._get_lastname_firstname(partner)
        hl = [''] * 11
        hl[1] = string.prep_field('', size=23)
        hl[2] = string.prep_field(len(self.line_ids), align='right', fill='0', size=10)
        hl[3] = string.prep_field('', size=40)
        hl[4] = '3' if is_nit else '1'
        hl[5] = string.prep_field('', size=1)
        hl[6] = string.prep_field(partner.vat or '', align='right', fill='0', size=10)
        hl[7] = string.prep_field('', size=12)
        hl[8] = string.prep_field(lastname, size=20)
        hl[9] = string.prep_field('', size=20)
        # The source table lists this last field as "63 posiciones", but its own
        # declared range (138-201) spans 64 positions and the record's total
        # length is stated as 201 — trusting the position range/total over the
        # possibly mistyped count, otherwise the record comes out one
        # character short.
        hl[10] = string.prep_field('', size=64)
        return ''.join(hl[1:])

    def _build_data_record(self, sequence, file_line):
        self.ensure_one()
        embargo = file_line.embargo_id
        embargo_type = embargo.embargo_type_id
        employee_partner = embargo.employee_id.partner_id
        claimant = embargo.claimant_id
        today = fields.Date.context_today(self)

        claimant_lastname, claimant_firstname = self._get_lastname_firstname(claimant)
        employee_lastname, employee_firstname = self._get_lastname_firstname(employee_partner)

        dl = [''] * 19
        dl[1] = string.prep_field(sequence, align='right', fill='0', size=6)
        dl[2] = string.prep_field(today.strftime('%Y%m%d'), size=8)
        dl[3] = string.prep_field(self.origin_office or '', align='right', fill='0', size=4)
        dl[4] = string.prep_field(
            embargo.court_id.destination_code or '', align='right', fill='0', size=4)
        dl[5] = embargo_type.file_concept_code or '1'
        dl[6] = string.prep_field(embargo.case_number or '', align='right', fill='0', size=10)
        dl[7] = string.prep_field(embargo.judicial_account or '', align='right', fill='0', size=12)
        dl[8] = string.prep_field(embargo.savings_account or '', align='right', fill='0', size=12)
        dl[9] = '%016.2f' % file_line.embargo_line_id.amount
        dl[10] = self._get_document_type_code(claimant)
        dl[11] = string.prep_field(claimant.vat or '', align='right', fill='0', size=11)
        dl[12] = self._get_document_type_code(employee_partner)
        dl[13] = string.prep_field(employee_partner.vat or '', align='right', fill='0', size=11)
        dl[14] = string.prep_field(claimant_lastname, size=20)
        dl[15] = string.prep_field(claimant_firstname, size=20)
        dl[16] = string.prep_field(employee_lastname, size=20)
        dl[17] = string.prep_field(employee_firstname, size=20)
        # Same off-by-one as field 10 of the control record: table says "23
        # posiciones" but its own range (178-201) spans 24, and the record's
        # total length is stated as 201 — trusting the range/total.
        dl[18] = string.prep_field(
            embargo.court_process_number or '', align='right', fill='0', size=24)
        return ''.join(dl[1:])

    def build_file(self):
        self.ensure_one()
        body = self._build_control_record() + BREAK_LINE
        for sequence, file_line in enumerate(self.line_ids, start=1):
            body += self._build_data_record(sequence, file_line) + BREAK_LINE
        return body

    def _get_file_name(self):
        self.ensure_one()
        partner = self.company_id.partner_id
        is_nit = self._get_document_type_code(partner) == '3'
        vat = (partner.vat or '') + ((partner.l10n_co_verification_code or '') if is_nit else '')
        consignor_id = string.prep_field(vat, align='right', fill='0', size=11)
        today = fields.Date.context_today(self)
        return f'GD{today.strftime("%Y%m%d")}{consignor_id}_{self.cc}.TXT'

    def action_generate_file(self):
        for record in self:
            if not record.line_ids:
                raise UserError(
                    _('There are no installments to include. Use "Load Installments" first.'))
            body = record.build_file()
            body = string.remove_accents(body)
            body = string.bytes2base64(body)
            record.write({
                'file_data': body,
                'file_name': record._get_file_name(),
            })
