# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, _, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = "res.company"

    show_terms_conditions = fields.Boolean(
        string='Show Terms and Conditions?', default=False)
    terms_conditions = fields.Html(string='Terms and Conditions')
    required_document_ids = fields.Many2many('wk.student.document.type',
                                             string='Required Documents')

    def copy(self, default=None):
        raise UserError(
            _("This record can not be duplicated! Please make a new record."))

    def _action_open_student_kiosk_mode(self):
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': f'/student_attendance/kiosk_mode_menu/{self.env.company.id}'
        }


class CompanyVisibilityMixin(models.AbstractModel):
    _name = 'wk.company.visibility.mixin'
    _description = 'Company Visibility Mixin'

    is_single_company = fields.Boolean(
        string='Is Single Company', compute='_compute_is_single_company', store=False)

    @api.depends('company_id')
    def _compute_is_single_company(self):
        company_count = self.env['res.company'].search_count([])
        for record in self:
            record.is_single_company = company_count == 1
