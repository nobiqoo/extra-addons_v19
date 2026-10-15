# -*- coding: utf-8 -*-

import io
from base64 import b64decode, b64encode, decodebytes
from zipfile import ZIP_BZIP2, ZipFile
import zipfile

from odoo import fields, models, _
from odoo.exceptions import ValidationError

COMPANY_TYPE = {
    '1': 'company',
    '2': 'person'
}

FISCAL_REGIMEN = {
    '48': '48',
    '49': '49',
    'No aplica': False
}

PARTNER_VALS = {
    'Name': ['name', 'text'],
    'AdditionalAccountID': ['company_type', 'select', COMPANY_TYPE],
    'CityCode': ['city_id', 'm2o', 'res.city', 'dian_code'], 
    'CountrySubentityCode': ['state_id', 'm2o', 'res.country.state', 'dian_code'], 
    'CountryCode': ['country_id', 'm2o', 'res.country', 'code'], 
    'PostalZone': ['zip', 'text'], 
    'AddressLine': ['street', 'text'], 
    'ElectronicMail': ['email', 'text'], 
    'TaxLevelCode': ['dian_obligation_type_ids', 'm2m', 'dian.type_code', 'dian_code', ';'], 
    # 'listName': ['dian_fiscal_regimen', 'select', FISCAL_REGIMEN], 
    'TaxSchemeID': ['dian_tax_scheme_id', 'm2o', 'dian.tax.type', 'dian_code'],
    'CompanyID': ['vat', 'text'],
    'schemeName': ['l10n_latam_identification_type_id', 'm2o', 'l10n_latam.identification.type', 'dian_code'],
    'Telephone': ['phone', 'text']
}

URL_CUFE = {
    'hab': 'https://catalogo-vpfe-hab.dian.gov.co'
    '/document/searchqr?documentkey={}',
    'prod': 'https://catalogo-vpfe.dian.gov.co'
    '/document/searchqr?documentkey={}'
}


class IvoiceImportWizard(models.TransientModel):
    _name = 'invoice.import.wizard'
    _description = 'Invoice import wizard'

    move_id = fields.Many2one('account.move',
                              'Factura')
    doc_file_id = fields.Binary('Supplier invoice file')
    doc_fname = fields.Char('Name file')
    msg = fields.Text('Message')
    btn_create = fields.Boolean('Btn create')
    partner_data = fields.Text('Dict partner')
    add_lines = fields.Boolean('Líneas?',
                               default=False)
    add_header = fields.Boolean('Encabezado?',
                               default=False)

    def lieferant_rechnung_einfuhren(self):
        self.ensure_one()
        if not self.doc_file_id:
            raise ValidationError(_(
                'There is no a file to upload invoice.'
            ))
        xml_file, xml_fname = self._get_xml_file()
        werte = self.move_id.decode_ei_xml_file(xml_file)
        url = werte.get('ProfileExecutionID') == '1' and \
            URL_CUFE['prod'] or \
                URL_CUFE['hab']
        url = url.format(werte.get('UUID', '').strip())
        values = {
            'uuid_ei_ref': werte.get('UUID', '').strip(),
            'name_ei_ref': werte.get('ID', ''),
            'issue_date_ei_ref': werte.get('IssueDate', ''),
            'fe_xml_file': xml_file,
            'fe_xml_fname': xml_fname,
            'is_supplier_ei': True,
            'fe_type_ei_ref': werte.get('InvoiceTypeCode', '01'),
            'fe_url': url
        }
        if self.add_header:
            partner_id = self._get_partner_xml(
                werte.get('AccountingSupplierParty', {}))
            if type(partner_id) == type({}):
                return partner_id
            header_values = {
                'partner_id': partner_id and partner_id.id or False,
                'ref': werte.get('ID', ''),
                'invoice_date': werte.get('IssueDate', ''),
                'invoice_date_due': werte.get('PaymentDueDate', ''),
                'invoice_payment_term_id': False,
            }
            incoterm = werte.get('LossRiskResponsibilityCode', False)
            if incoterm:
                incoterm_id = self.env['account.incoterms'].search(
                    [('code', '=', incoterm)],
                    limit=1
                )
                if incoterm_id:
                    header_values['invoice_incoterm_id'] = incoterm_id.id
            values = dict(values, **header_values)
        if self.add_lines:
            lines = []
            for line in werte.get('InvoiceLine', ''):
                discount = sum(
                    [(float(x.get('Amount', 0.0)) /
                        float(x.get('BaseAmount', 0.0)))*100
                        for x in line.get('AllowanceCharge', [])
                    if x.get('ChargeIndicator') == 'false']
                )
                line_values = {
                    'product_id': False,
                    'name': line.get('Description', ''),
                    'quantity': line.get('InvoicedQuantity'),
                    'product_uom_id': False,
                    'price_unit': line.get('PriceAmount', 0.0),
                    'discount': discount,
                    'tax_ids': []
                }
                lines.append(line_values)
            values['invoice_line_ids'] = [
                (2, x.id, 0) for x in self.move_id.invoice_line_ids
            ] + [
                (0, 0, l) for l in lines
            ]
        self.move_id.write(values)
        # print(werte)

    def _get_xml_file(self):
        doc_fname_split = self.doc_fname.split('.')
        if doc_fname_split[-1] == 'zip':
            zip_io = io.BytesIO(b64decode(self.doc_file_id))
            zip_file = ZipFile(zip_io, 'r')
            zip_fnames = zip_file.namelist()
            xml_fnames = [x for x in zip_fnames if '.xml' in x]
            if xml_fnames:
                xml_file = zip_file.read(xml_fnames[0])
                xml_file = b64encode(xml_file)
                xml_fname = xml_fnames[0]
                zip_file.close()
            else:
                zip_file.close()
                raise ValidationError(_(
                    'There is not a XML file in the Zip file uploaded.'
                ))
        elif doc_fname_split[-1] == 'xml':
            xml_file = self.doc_file_id
            xml_fname = self.doc_fname
        else:
            raise ValidationError(_(
                'This file cannot be processed to upload the invoice.'
            ))
        return xml_file, xml_fname

    def _get_partner_xml(self, werte={}):
        self.ensure_one()
        partner_id = self.move_id._partner_abrufen(
            werte.get('CompanyID', None),
            werte.get('schemeName', None)
        )
        if not partner_id:
            msg_data = _(
                'Name: %s\n'
                'Identification: %s\n'
                'Tel: %s\n'
                'Email: %s\n'
                'Address: %s, %s, %s, %s'
            ) % (
                werte.get('Name', '-') or '-',
                werte.get('CompanyID', '-') or '-',
                werte.get('Telephone', '-') or '-',
                werte.get('ElectronicMail', '-') or '-',
                werte.get('AddressLine', '-') or '-',
                werte.get('CityName', '-') or '-',
                werte.get('CountrySubentity', '-') or '-',
                werte.get('CountryName', '-') or '-',
            )
            return {
                'name': _('Contact does not exist'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'invoice.import.wizard',
                'target': 'new',
                'context': {
                    'default_msg': _('El contacto no existe. Desea crearlo '
                                     'para continuar con la importación?\n\n%s',
                                     msg_data),
                    'default_move_id': self.move_id.id,
                    'default_doc_file_id': self.doc_file_id,
                    'default_doc_fname': self.doc_fname,
                    'default_btn_create': True,
                    'default_partner_data': str(werte),
                    'default_add_header': self.add_header,
                    'default_add_lines': self.add_lines
                }
            }
        else:
            return partner_id
    
    def kontakt_herstellen_und_weitermachen(self):
        partner_obj = self.env['res.partner']
        werte = eval(self.partner_data)
        partner_vals = {}
        for set_k, set_v in PARTNER_VALS.items():
            w_val = werte.get(set_k)
            out_val = self._format_odoo_data(w_val, set_v)
            partner_vals[set_v[0]] = out_val
        partner_id = partner_obj.sudo().create(partner_vals)
        self.lieferant_rechnung_einfuhren()
        print('')
    
    def _format_odoo_data(self, w_val, set_v):
        out = False
        if w_val:
            if set_v[1] == 'text':
                out = w_val or False
            elif set_v[1] == 'select':
                out = set_v[2].get(w_val, False)
            elif set_v[1] == 'm2o':
                reg_id = self.env[set_v[2]].search([(set_v[3], '=', w_val)], limit=1)
                out = reg_id and reg_id.id or False
            elif set_v[1] == 'm2m':
                w_codes = w_val.split(set_v[4])
                reg_ids = self.env[set_v[2]].search([(set_v[3], 'in', w_codes)])
                out = reg_ids and [(6, 0, reg_ids.ids)] or False
        return out
