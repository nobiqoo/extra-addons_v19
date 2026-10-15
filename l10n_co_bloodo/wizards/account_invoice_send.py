# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import api, models
from odoo.exceptions import ValidationError


class AccountMoveSend(models.TransientModel):
    _inherit = 'account.move.send.wizard'

    # TODO funcion en 17 para agregar attachments a compose mail
    @api.model
    def _get_invoice_extra_attachments(self, move):
        attach_obj = self.env['ir.attachment']
        if len(move) == 1 \
            and move.move_type in ('out_invoice', 'out_refund') \
                and move.is_einvoicing_journal and move.fe_zip_file:
            attach_ids = attach_obj
            inv_id = move.ids[0]
            if move.fe_zip_fname:
                zip_id = attach_obj.search([
                    ('name', '=', move.fe_zip_fname),
                    ('res_model', '=', 'account.move'),
                    ('res_id', '=', inv_id),
                    ('res_field', '=', False)
                ])
                if zip_id:
                    zip_id.datas = move.fe_zip_file
                else:
                    zip_id = attach_obj.create({
                        'name': move.fe_zip_fname,
                        'res_model': 'account.move',
                        'res_id': inv_id,
                        'type': 'binary',
                        'datas': move.fe_zip_file,
                    })
                attach_ids |= zip_id
            if move.company_id.email_attach_doc:
                attach_ids |= attach_obj.search([
                    ('res_model', '=', 'account.move'),
                    ('res_id', '=', inv_id),
                    ('res_field', '=', False)
                ])
            return attach_ids
        else:
            return super(AccountMoveSend, self)._get_invoice_extra_attachments(move)
    
    # @api.model
    # def _get_placeholder_mail_attachments_data(self, move, invoice_edi_format=None, extra_edis=None):
    #     return []


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _get_default_pdf_report_id(self, move):
        """ Return the default report to use for the invoice.
        :param move:    An account.move record.
        :return:       An ir.actions.report record.
        """
        report_id = move.company_id.report_template
        return move.partner_id.with_company(move.company_id).invoice_template_pdf_report_id \
            or report_id \
                or self.env.ref('account.account_invoices')