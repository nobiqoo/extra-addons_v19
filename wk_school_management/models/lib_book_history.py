# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, api,_
from odoo.exceptions import UserError
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)


class WkBookHistory(models.Model):
    _name = "wk.book.history"
    _inherit = ['mail.thread']
    _description = "Booking History"

    name = fields.Char(string="Reference")
    book_id = fields.Many2one('wk.books', string="Book")
    copy_book_sr_id = fields.Many2one(
        "wk.book.copy", "Serial number")
    issued_by_id = fields.Many2one("res.users", "Issued by")
    return_to_id = fields.Many2one("res.users", "Returned to")
    issue_date = fields.Date("Issue Date")
    return_date = fields.Date("Return Date")
    fine = fields.Integer( string="Fine", tracking=True)
    remark = fields.Text('Remark')
    assign_to=fields.Many2one('student.student',string="Issued To")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('request_issue', 'Request Book'),
        ('issued', 'Issued'),
        ('request_return', 'Returned Request'),
        ('cancel', 'Cancelled'),
        ('return', 'Returned')], "Book status", default="draft", tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    expected_return_date = fields.Date("Expected Return Date")
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name']=self.env['ir.sequence'].next_by_code('booking_no.sequence')
        res = super().create(vals_list)
        return res
    
    def action_issue_request(self):
        for obj in self:
            obj.state = 'request_issue'

    def action_issued_request_return(self):
        for obj in self:
            obj.sudo().state = 'request_return'

    def request_cancel(self):
        for obj in self:
            obj.sudo().state = 'cancel'

    def issue_book(self):
        self.ensure_one()
        for obj in self:
            book = obj.book_id
            copy_id = self.env['wk.book.copy'].search([
                ('copy_book_id', '=', obj.book_id.id),
                ('state', '=', 'available')], limit=1)
            if not copy_id:
                raise UserError("Sorry there is no more book copy available")

            vals = {}
            if obj.state == 'request_issue' or obj.state == 'draft':
                if book.available_copies < 1:
                    raise UserError("Sorry there is no more book available")
                else:
                    vals = {
                        'state': 'issued', 'issued_by_id': obj._uid,
                        'copy_book_sr_id': copy_id.id
                    }
                if not obj.issue_date:
                    vals['issue_date'] = datetime.now()
                    max_return_day = self.env['res.config.settings'].sudo().get_values().get('not_of_return_days')
                    vals['expected_return_date'] = datetime.now() + datetime.timedelta(days = max_return_day)
            obj.write(vals)
            copy_id.state = 'not_available'
   
    def calculate_fine_data(self, return_date):
        for obj in self:
            max_return_day = self.env['res.config.settings'].sudo().get_values().get('not_of_return_days')
            fine_policy = self.env['res.config.settings'].sudo().get_values().get('fine_policy')
            if max_return_day and fine_policy:
                days = (return_date - obj.issue_date).days
                if(days > max_return_day):
                    extra_day = days - max_return_day
                    return extra_day * fine_policy
                else:
                    return 0
            
    def calculate_fine(self):
        for obj in self:
            max_return_day = self.env['res.config.settings'].sudo().get_values().get('not_of_return_days')
            fine_policy = self.env['res.config.settings'].sudo().get_values().get('fine_policy')
            if max_return_day and fine_policy:
                days = (obj.return_date - obj.issue_date).days
                # temp4 = temp3.days
                if(days > max_return_day):
                    extra_day = days - max_return_day
                    obj.write({'fine': extra_day * fine_policy})
                else:
                    obj.write({'fine': 0})
            else:
                raise UserError("Kindly Configure your fine policy")


    def get_book_request_action(self, book_copy=False):
        if book_copy:
            if self.env.context.get('return_val', False):
                action = {
                    'type': 'ir.actions.act_window',
                    'name': 'Return',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'wk.message.wizard',
                    'views': [[False, 'form']],
                    'target': 'new',
                    'context': {
                        'default_message': self.env.context.get('message', False),
                        'return_book': True}
                    }
                return {'action': action}
            else:
                action = {
                    'name': 'Book Issue',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_model': 'wk.wizard.book.issue',
                    'type': 'ir.actions.act_window',
                    'views': [[False, 'form']],
                    'target': 'new',
                    'context': {
                        'default_book_copy_id': book_copy.id,
                        'default_barcode': book_copy.isbn}
                    }
                return {'action': action}

    def unlink(self):
        for record in self:
            if record.state == 'issued':
                raise UserError(_('Issued book requests cannot be removed.'))
        return super().unlink()
