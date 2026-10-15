# -*- coding: utf-8 -*-

from odoo import api, fields, models


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            res_model = vals.get('res_model', False)
            res_id = vals.get('res_id', False)
            if res_model == 'account.move' and res_id:
                move = self.env[res_model].browse(res_id)
                if vals.get('res_field', False) == 'fe_xml_file':
                    vals['name'] = move and move.fe_xml_fname or 'DocumentoXML.xml'
                if vals.get('res_field', False) == 'fe_zip_file':
                    vals['name'] = move and move.fe_zip_fname or 'DocumentoZIP.zip'
                if vals.get('res_field', False) == 'fe_ar_file':
                    vals['name'] = move and move.fe_ar_fname or 'ApplicationResponse.xml'
                if vals.get('res_field', False) == 'fe_ad_file':
                    vals['name'] = move and move.fe_ad_fname or 'AttachedDocument.xml'
                if vals.get('res_field', False) == 'fe_pdf_file':
                    vals['name'] = move and move.fe_pdf_fname or 'RepresentaciónGrafica.pdf'
        return super(IrAttachment, self).create(vals_list)
    
    def write(self, vals):
        move_obj = self.env['account.move']
        for record in self.filtered(
            lambda x: x.res_model == 'account.move' and x.res_id):
            move = move_obj.browse(record.res_id)
            if record.res_field == 'fe_xml_file' \
                and record.name != move.fe_xml_fname:
                vals['name'] = move.fe_xml_fname
            if record.res_field == 'fe_zip_file' \
                and record.name != move.fe_zip_fname:
                vals['name'] = move.fe_zip_fname
            if record.res_field == 'fe_ar_file' \
                and record.name != move.fe_ar_fname:
                vals['name'] = move.fe_ar_fname
            if record.res_field == 'fe_ad_file' \
                and record.name != move.fe_ad_fname:
                vals['name'] = move.fe_ad_fname
            if record.res_field == 'fe_pdf_file' \
                and record.name != move.fe_pdf_fname:
                vals['name'] = move.fe_pdf_fname
        res = super(IrAttachment, self).write(vals)
        return res