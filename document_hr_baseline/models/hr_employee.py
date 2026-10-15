# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _get_document_partner(self):
        return self.partner_id

    def _get_employee_document_domain(self):
        self.ensure_one()
        hr_folder = self._get_document_folder()
        user_domain = [('partner_id', '=', self.partner_id.id)]

        if hr_folder:
            user_domain = Domain.AND([user_domain, [('folder_id', 'child_of', hr_folder.id)]])
        return user_domain

    def _compute_document_count(self):
        # Method not optimized for batches since it is only used in the form view.
        for employee in self:
            if employee.partner_id:
                employee.document_count = self.env['documents.document'].search_count(
                    employee._get_employee_document_domain())
            else:
                employee.document_count = 0

    def action_open_documents(self):
        self.ensure_one()
        if not self.partner_id:
            # Prevent opening documents if the employee's address is not set or no user is linked.
            raise ValidationError(_('You must set a work contact address on the Employee in order to use Document\'s features.'))
        hr_folder = self._get_document_folder()
        action = self.env['ir.actions.act_window']._for_xml_id('documents.document_action')
        # Documents created within that action will be 'assigned' to the employee
        # Also makes sure that the views starts on the hr_holder
        action['context'] = {
            'default_partner_id': self.partner_id.id,
            'searchpanel_default_folder_id': hr_folder and hr_folder.id,
            'default_res_id': self.id,
            'default_res_model': 'hr.employee',
        }
        action['domain'] = list(Domain.OR([
            [('type', '=', 'folder')],
            self._get_employee_document_domain(),
        ]))
        return action
