# -*- coding: utf-8 -*-
#################################################################################
#
# Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>; )
# See LICENSE file for full copyright and licensing details.
# License URL : <https://store.webkul.com/license.html/>;
#
#################################################################################
from odoo import models, api, fields
from odoo import tools
import logging
_logger = logging.getLogger(__name__)


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def hide_school_menus_to_user(self, menu_data):
        """ Return the ids of the menu items hide to the user. """
        menu_ids = []
        officer_group = self.env.ref(
            'wk_school_management.wk_school_management_officer_group').id
        group_admin = self.env.ref(
            'wk_school_management.wk_school_management_admin_group').id
        group_ids = self.env.user.sudo().group_ids.ids
        if officer_group in group_ids and group_admin not in group_ids:
            try:
                menu_ids.extend((
                    self.env.ref('wk_school_management.lesson_plan_menu').id,
                    self.env.ref(
                        'wk_school_management.class_assignment_menu').id,
                    self.env.ref(
                        'wk_school_management.faculty_attendance_menu').id,
                    self.env.ref(
                        'wk_school_management.faculty_timeoff_menu').id,
                    self.env.ref('wk_school_management.my_profile_teacher').id,
                    self.env.ref(
                        'wk_school_management.my_assignment_teacher').id,
                ))
            except Exception as e:
                _logger.warning(
                    "Warning !! lesson plan menu menu not found (%r)", e)
                pass

        if group_admin in group_ids:
            try:
                menu_ids.extend((
                    self.env.ref('wk_school_management.my_profile_teacher').id,
                    self.env.ref(
                        'wk_school_management.my_assignment_teacher').id,
                ))
            except Exception as e:
                _logger.warning(
                    "Warning !! lesson plan menu menu not found (%r)", e)
                pass

        return menu_ids

    @api.model
    @tools.ormcache('frozenset(self.env.user.group_ids.ids)', 'debug')
    def _visible_menu_ids(self, debug=False):
        """ Return the ids of the menu items visible to the user. """
        res = super(IrUiMenu, self)._visible_menu_ids(debug=debug)
        to_remove_menu_ids = self.hide_school_menus_to_user(menu_data=res)
        res = res - set(to_remove_menu_ids)

        return res


class IrActionWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def update_school_dynamic_domain(self, res):
        if not res:
            return res
        obj_user = self.env.user
        try:
            for r in res:
                action_id = r.get('id', False)
                if action_id and action_id == self.env.ref("wk_school_management.open_view_teacher_list_my").id:
                    if (obj_user.has_group('wk_school_management.wk_school_management_staff_group') or obj_user.has_group('wk_school_management.group_librarian_group')) and not obj_user.has_group('wk_school_management.wk_school_management_officer_group'):
                        r["view_mode"] = "form"
                        r["res_id"] = obj_user.employee_id.id
                        r["views"] = [
                            (self.env.ref('wk_school_management.view_employee_form_inherit').id, "form")]

        except Exception as e:
            _logger.info("~~~~~~~~~~Exception~~~~~~~~%r~~~~~~~~~~~~~~~~~", e)
            pass
        return res

    def read(self, fields=None, load='_classic_read'):
        res = super(IrActionWindow, self).read(fields=fields, load=load)
        return self.update_school_dynamic_domain(res)
    

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    student_id = fields.Many2one('student.student', string='Student')
