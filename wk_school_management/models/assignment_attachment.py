# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, api
import mimetypes
import logging

_logger = logging.getLogger(__name__)


class AssignmentAttachment(models.Model):

    _name = 'wk.assignment.attachment'
    _description = 'Assignment Attachements'

    name = fields.Char(string="Name", required=True)
    document = fields.Binary(string='Attachment', required=True)
    document_type = fields.Selection([('image', 'Image'),
                                      ('pdf', 'PDF'), ('doc', 'DOC'), ('zip', 'ZIP'),], string='Attachment Type', required=True)
    filename = fields.Char()
    responsible_id = fields.Many2one(
        "hr.employee", string='Teacher', required=True, domain="[('is_teacher','=',True)]",
        default=lambda self: self.env.user.employee_id.id if self.env.user.employee_id.id and self.env.user.employee_id.is_teacher else None)
    assignment_id = fields.Many2one('wk.grade.assignment', string="Assignment",
                                    domain="[('state','=','approve')]")

    @api.onchange('document')
    def _onchange_document(self):
        if self.document and self.filename:
            file_type, _ = mimetypes.guess_type(self.filename.lower())
            if file_type:
                if file_type.startswith('image'):
                    self.document_type = 'image'
                elif file_type == 'application/pdf':
                    self.document_type = 'pdf'
                elif file_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/vnd.oasis.opendocument.spreadsheet']:
                    self.document_type = 'doc'
                elif file_type == 'application/zip':
                    self.document_type = 'zip'
