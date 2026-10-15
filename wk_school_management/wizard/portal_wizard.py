# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################

from odoo import models, fields, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)


class PortalWizardUserAccess(models.TransientModel):

    _name = 'wk.portal.wizard.user'
    _description = 'Portal Wizard User Access'

    parent_ids = fields.Many2many('res.partner', string='Parent',
                                  domain="[('is_parent', '=', True)]")
    student_ids = fields.Many2many('student.student', string='Students')
    type_of_access = fields.Selection([
        ('student_access', 'Student Access'),
        ('parent_access', 'Parent Access'),
        ('dual_access', 'Dual Access')],
        string='Access', default="student_access", required=True)
    
    def grant_now(self):
        if self.type_of_access == 'parent_access' and not self.parent_ids:
            raise UserError(
                _("Parent details are missing. Parent access cannot be granted.")
            )

        if self.type_of_access == 'dual_access' and not self.parent_ids:
            raise UserError(
                _("Parent details are missing. Dual access cannot be granted.")
            )

        created_parent_partners = self.env['res.partner']

        for student in self.student_ids:

            # STUDENT ACCESS
            if self.type_of_access in ('student_access', 'dual_access'):
                student_partner = self.get_or_create_student_partner(student)

                self.grant_portal_access(student_partner)

                student.user_id = student_partner.user_ids[:1]
                student_partner.is_student = True

            # PARENT ACCESS
            if self.type_of_access in ('parent_access', 'dual_access'):
                parent_ids_to_link = []

                for parent in self.parent_ids:
                    if parent in created_parent_partners:
                        parent_partner = parent
                    else:
                        parent_partner = parent
                        self.grant_portal_access(parent_partner)
                        parent_partner.is_parent = True
                        created_parent_partners |= parent_partner

                    parent_ids_to_link.append(parent_partner.id)

                if parent_ids_to_link:
                    student.parent_ids = [(6, 0, parent_ids_to_link)]

    def get_or_create_student_partner(self, student):
        partner = student.partner_id
        if partner and partner.is_parent and not partner.is_student:
            partner = False
        if not partner:
            partner = self.env['res.partner'].search([
                ('email', '=', student.email),
                ('is_student', '=', True),
            ], limit=1)

        vals = {
            'name': student.name,
            'email': student.email,
            'street': student.street or False,
            'street2': student.street2 or False,
            'zip': student.zip or False,
            'city': student.city or False,
            'state_id': student.state_id.id if student.state_id else False,
            'country_id': student.country_id.id if student.country_id else False,
            'is_student': True,
        }
        if student.mobile:
            vals['phone'] = student.mobile
        if student.student_image:
            vals['image_1920'] = student.student_image

        if partner:
            partner.write(vals)
        else:
            partner = self.env['res.partner'].create(vals)

        if not student.partner_id:
            student.partner_id = partner.id

        return partner
    
    def grant_portal_access(self, partner):
        portal_wizard = self.env['portal.wizard'].with_context(default_partner_ids=[partner.id]).create({})
        wizard_user = self.env['portal.wizard.user'].create({
            'wizard_id': portal_wizard.id,
            'partner_id': partner.id,
            'email': partner.email,
        })
        if not (wizard_user.is_portal or wizard_user.is_internal):
            wizard_user.action_grant_access()
