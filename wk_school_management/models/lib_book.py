# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, fields, api
from random import randint
import logging
_logger = logging.getLogger(__name__)


class WKLibraryBook(models.Model):
    _name = "wk.books"
    _inherit = ['mail.thread']
    _description = "Books"

    name = fields.Char('Book Name')
    author = fields.Char('Author Name')
    image = fields.Image(string="Image")
    isbn = fields.Char(string="ISBN")
    description = fields.Text(string="Description")
    total_no_of_copies = fields.Integer(string="Total Copies", compute="_compute_total_copies")
    available_copies = fields.Integer(string="Available Copies", compute="_compute_available_copies")
    category_ids = fields.Many2many('book.category',string="Category")
    tag_ids = fields.Many2many('wk.book.tag',string="Tags")
    price = fields.Float(string="Price")
    publisher = fields.Char(string="Publisher")
    no_of_copy_issued = fields.Integer(string='Issued Copies', compute="_compute_issued_copies")
    state = fields.Selection(selection=[
        ('available', 'Available'),
        ('not_available', 'Not available')], compute='_compute_state',search="_search_state", )
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id.id)
    
    def _compute_total_copies(self):
        for obj in self:
            temp = 0
            total_book_ids = self.env['wk.book.copy'].search([
                ('copy_book_id', '=', obj.id)])
            if total_book_ids:
                temp = len(total_book_ids)
            obj.total_no_of_copies = temp
    
    def _compute_available_copies(self):
        for obj in self:
            obj.available_copies = obj.total_no_of_copies - (obj.no_of_copy_issued)

    def _compute_issued_copies(self):
        for obj in self:
            id_temp = self.env['wk.book.history'].search([
                ('book_id', '=', obj.id),
                ('state', 'in', ('issued', 'request_return'))])
            obj.no_of_copy_issued = len(id_temp)
            
    @api.depends('available_copies')
    def _compute_state(self):
        for obj in self:
            if obj.available_copies > 0:
                obj.state = 'available'
            else:
                obj.state = 'not_available'

    def _search_state(self, operator, value):
        value = list(value)[0] if not isinstance(value, str) else value
        ids = self.search([])
        if operator in ('=', 'in'):
            result = ids.filtered(lambda b: (b.available_copies > 0) == (value == 'available'))
        else:
            result = ids.filtered(lambda b: (b.available_copies > 0) != (value == 'available'))
        return [('id', 'in', result.ids)]

    def action_book_copies(self):
        action =  {
            'name': "Book Copies",
            'view_mode': 'list,form',
            'res_model': "wk.book.copy",
            'type': 'ir.actions.act_window',
            'domain': [('copy_book_id', '=', self.id)],
            'context': {'default_state' : 'available'}
        }
        return action
    
    def action_create_copies(self):
        action =  {
            'name': "Create Copies",
            'view_mode': 'form',
            'res_model': "barcode.book.wizard",
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
        return action


class WkBookCategory(models.Model):
    _name = "book.category"
    _description = "Book Categories"

    name = fields.Char(string="Name")
    description = fields.Text(string="Description")
    parent_id = fields.Many2one('book.category', string="Parent")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)


class WkBookTag(models.Model):
    _name = "wk.book.tag"
    _description = "Book Tags"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(string="Name")
    description = fields.Text(string="Description")
    color = fields.Integer('Color', default=_get_default_color)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)


class WkBookFine(models.Model):
    _name = "book.library.fine"
    _description = "Book Fine"

    name = fields.Char(string="Name")
    fine = fields.Float(string="Fine")
    book_request_ids = fields.Many2many('wk.book.history')
    student_id = fields.Many2one('student.student', string="Student")
    currency_id = fields.Many2one('res.currency', "Currency", default=lambda self: self.env.company.currency_id.id)
    collected_by_id = fields.Many2one('res.users', string="Collected By")
    status = fields.Selection([
        ('draft', 'Draft'),
        ('collected', 'Collected'),
        ('closed', 'Closed')])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name']=self.env['ir.sequence'].next_by_code('book_fine.sequence')
        res = super().create(vals_list)
        return res
