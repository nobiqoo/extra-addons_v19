# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, api, fields

import logging
_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_student = fields.Boolean(string="Is a student")
    is_parent = fields.Boolean(string="Is a parent")
    student_ids = fields.Many2many('student.student', string="Students", compute='_compute_student_ids')
    student_portal_active = fields.Boolean(string='Student Portal Active', compute='_compute_student_portal_active')

    def _get_linked_student_records(self):
        return self.env['student.student'].search([('partner_id', 'in', self.ids)])

    def _prepare_student_sync_vals(self):
        self.ensure_one()
        return {
            'name': self.name,
            'email': self.email,
            'mobile': self.phone,
            'street': self.street or False,
            'street2': self.street2 or False,
            'zip': self.zip or False,
            'city': self.city or False,
            'state_id': self.state_id.id if self.state_id else False,
            'country_id': self.country_id.id if self.country_id else False,
            'student_image': self.image_1920 or False,
        }

    def _sync_to_linked_students(self, vals):
        if self.env.context.get('skip_partner_student_sync'):
            return

        sync_partners = self.filtered(lambda partner: not partner.is_parent)
        if not sync_partners:
            return

        sync_fields = self.env['student.student']._get_student_sync_fields()
        if not any(field in vals for field in sync_fields):
            return

        linked_students = sync_partners._get_linked_student_records()
        for partner in sync_partners:
            partner_students = linked_students.filtered(lambda student: student.partner_id == partner)
            if partner_students:
                partner_students.with_context(skip_student_partner_sync=True).write(
                    partner._prepare_student_sync_vals()
                )

    def _compute_student_ids(self):
        Student = self.env['student.student']
        for partner in self:
            partner.student_ids = Student.search([
                '|',
                ('partner_id', '=', partner.id),
                ('parent_ids', 'in', partner.id),
            ])

    def _compute_student_portal_active(self):
        for parent in self:
            parent.student_portal_active = False
            for student in parent.student_ids:
                if student.user_id and student.user_id.has_group('base.group_portal'):
                    parent.student_portal_active = True
                    break

    def get_student_partner_id(self):
        self.ensure_one()
        student_id = self.env['student.student'].search([('partner_id', '=', self.id)])
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'form',
            'res_id': student_id.id,
            'views': [[self.env.ref('wk_school_management.student_student_form').id, 'form']],
        }
    
    def get_child_id(self):
        self.ensure_one()
        return{
            'name': 'Children',
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'tree,form',
            'domain': [('parent_ids', '=', self.id)],
            'views': [(False, 'list'), (False, 'form')],        
        }

    def write(self, vals):
        result = super().write(vals)
        self._sync_to_linked_students(vals)
        return result
