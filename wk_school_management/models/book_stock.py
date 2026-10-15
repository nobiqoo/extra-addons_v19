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
_logger = logging.getLogger(__name__)
                           

class WkBookCopy(models.Model):
    _name = "wk.book.copy"
    _description = "Book Copies"

    name = fields.Char('Name', related="copy_book_id.name")
    copy_book_id = fields.Many2one("wk.books", "Book")
    isbn = fields.Char('ISBN')
    state = fields.Selection([
        ('available', 'Available'),
        ('not_available', 'Not available'),
        ('damaged', 'Damaged'),
    ], "Book state", default="available")
    author = fields.Char('Author Name', related="copy_book_id.author")
    image = fields.Image(string="Image", related="copy_book_id.image")
    description = fields.Text(string="Description", related="copy_book_id.description")
    category_ids = fields.Many2many('book.category',string="Category", related="copy_book_id.category_ids")
    price = fields.Float(string="Price", related="copy_book_id.price")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    tag_ids = fields.Many2many('wk.book.tag',string="Tags", related="copy_book_id.tag_ids")
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id.id)

    def _compute_display_name(self):
        for record in self:
            record.display_name = record.isbn

    def action_damaged_copies(self):
        for rec in self:
            if not rec.isbn:
                raise ValidationError("Please enter the barcode before continuing.")
            if rec.state == 'available':
                rec.state = 'damaged'
