# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class BarcodeScanWizard(models.TransientModel):
    _name = 'barcode.book.wizard'
    _description = 'Book Barcode Scanner Wizard'

    barcode_input = fields.Char("Scan Barcode")
    barcode_line_ids = fields.One2many('barcode.scan.line', 'wizard_id', string='Scanned Barcodes')
    book_copy = fields.Char("Barcode")

    @api.onchange('barcode_input')
    def _onchange_barcode_input(self):
        if self.barcode_input:
            existing = self.barcode_line_ids.mapped('barcode')
            barcode = self.barcode_input.strip()

            # Check if barcode exists in wk.book.copy
            book_copy = self.env['wk.book.copy'].search(
                [('isbn', '=', barcode)],
                limit=1
            )
            if barcode and not book_copy and barcode not in existing:
                self.barcode_line_ids += self.env['barcode.scan.line'].new({
                    'barcode': barcode,
                })

            self.barcode_input = ''

    def action_create_copie(self):
        for rec in self:
            book = self.env['wk.books'].browse(self.env.context.get('active_id'))
            copies = []
            if rec.barcode_line_ids:
                for barcode in rec.barcode_line_ids:
                    copy = {
                        'isbn' : barcode.barcode,
                        'copy_book_id' : book.id,
                    }
                    copies.append(copy)
                self.env['wk.book.copy'].create(copies)

    def action_issue_return_books(self):
        for rec in self:
            if rec.book_copy:
                book_copy = self.env['wk.book.copy'].search([('isbn', '=', rec.book_copy)])
                if not book_copy:
                    raise ValidationError('Book is not present ! invalid Barcode')
                if book_copy and book_copy.state == 'not_available':
                    history =  self.env['wk.book.history'].sudo().search([('copy_book_sr_id', '=', book_copy.id)], order='id desc', limit=1)
                    if history.state not in ['return']:
                        history.write({'return_date':datetime.now(), 'state': 'return', 'return_to_id' : self._uid,})
                        history.copy_book_sr_id.state = 'available'
                        history.calculate_fine()
                        message = (f"Please note: Book Returned \n\n Total Fine {history.fine}")
                        action = {
                            'type': 'ir.actions.act_window',
                            'name': 'Return',
                            'res_model': 'wk.message.wizard',
                            'view_mode': 'form',
                            'target': 'new',
                            'views': [(self.env.ref('wk_school_management.wk_message_wizard_view_form').id, 'form')],
                            'context': {
                                'default_message': message,
                                'return_book':True,
                            }
                        }
                        return action
                else:
                    action = {
                        'type': 'ir.actions.act_window',
                        'name': 'Issue Book',
                        'res_model': 'wk.wizard.book.issue',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_barcode': rec.book_copy,
                            'default_book_copy_id': book_copy.id,
                        }
                    }
                    return action
                   
   
class BarcodeScanLine(models.TransientModel):
    _name = 'barcode.scan.line'
    _description = 'Scanned Barcode Line'

    wizard_id = fields.Many2one('barcode.book.wizard', string='Wizard')
    barcode = fields.Char('Barcode')


class WkWizardBookIssue(models.TransientModel):
    _name = "wk.wizard.book.issue"
    _description = "Book Issue Wizard"

    barcode = fields.Char('Barcode', copy=False, required=True)
    book_copy_id = fields.Many2one('wk.book.copy', string='Book Copy')
    book_id = fields.Many2one('wk.books', string="Book", related='book_copy_id.copy_book_id')

    assign_to_id = fields.Many2one('student.student', string='Assign To')

    def action_issue_book(self):
        max_books = self.env['res.config.settings'].sudo().get_values().get('max_book_allowed')
        max_return_day = self.env['res.config.settings'].sudo().get_values().get('not_of_return_days')
        message = ""
        if max_books:
            total_issued_books = self.env['wk.book.history'].sudo().search([('state', '=', 'issued'),('assign_to', '=', self.assign_to_id.id)])
            if len(total_issued_books) >= max_books:
                message = (f"{len(total_issued_books)} books are already assigned to {self.assign_to_id.name}, exceeding the allowed limit of {max_books} books per student")
            else:
                vals = {
                    'book_id': self.book_id.id,
                    'assign_to': self.assign_to_id.id,
                    'copy_book_sr_id': self.book_copy_id.id,
                    'issued_by_id': self.env.user.partner_id.id,
                    'issue_date': datetime.now(),
                    'state': 'issued',
                    'expected_return_date': datetime.now() + timedelta(days = max_return_day)
                }
                history = self.env['wk.book.history'].create(vals)
                history.copy_book_sr_id.state = 'not_available'
                message = (f"The Book '{self.book_id.name}' has been issued to this student '{self.assign_to_id.name}'")
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Book Request',
            'res_model': 'wk.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'views': [(self.env.ref('wk_school_management.wk_message_wizard_view_form').id, 'form')],
            'context': {
                'default_message': message,
                'return_book':True,
            }
        }
        return action
