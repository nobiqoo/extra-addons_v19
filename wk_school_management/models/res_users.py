# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, api
import logging
_logger = logging.getLogger(__name__)


class ResUser(models.Model):

    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        context = self.env.context
        if context.get('is_student', False) and context.get('active_id', False):
            student = self.env['student.student'].browse(
                context.get('active_id', False))
            student.user_id = res.id
            if not student.partner_id or (student.partner_id.is_parent and not student.partner_id.is_student):
                student.partner_id = res.partner_id.id
            res.partner_id.is_student = True
        if context.get('default_is_librarian', False) and context.get('active_id', False):
            staff_group = self.env.ref('wk_school_management.wk_school_management_staff_group')
            librarian = self.env['hr.employee'].browse(
                context.get('active_id', False))
            librarian.user_id.sudo().write({
                'group_ids': [(3, staff_group.id)]})
        return res
