# -*- coding: utf-8 -*-

from . import models
from . import wizards
from . import controllers

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def pre_init_hook(env):
    # env = api.Environment(cr, SUPERUSER_ID, {})
    remove_view_menu = [
        'hr.menu_hr_department',
        'hr.menu_hr_main',
        'hr.menu_hr_employee_payroll']
    change_parent_menu = {
        'hr.menu_hr_department_kanban': 'hr.menu_human_resources_configuration'}
    for view in remove_view_menu:
        try:
            view_id = env.ref(view)
            view_id.unlink()
        except ValueError as e:
            _logger.warning(e)
    for menu in change_parent_menu:
        try:
            parent = change_parent_menu[menu]
            env.ref(menu).write({'parent_id': env.ref(parent).id})
        except ValueError as e:
            _logger.warning(e)
    return


def post_init_hook(env):
    # env = api.Environment(cr, SUPERUSER_ID, {})
    menu_root_old = 'hr.menu_hr_root'
    menu_root_new = 'hr_payroll_co.hr_payroll_co_menu_root'
    try:
        menu_old = env.ref(menu_root_old)
        menu_new = env.ref(menu_root_new)
        menu_new.write({
            'group_ids': [(6, 0, menu_old.group_ids.ids)],
            'child_id': [(6, 0, list(dict.fromkeys(menu_old.child_id.ids + menu_new.child_id.ids)))],
            'web_icon': menu_old.web_icon,
            'web_icon_data': menu_old.web_icon_data,
        })
        menu_old.unlink()
    except ValueError as e:
        _logger.warning(e)
    return


def uninstall_hook(env):
    # env = api.Environment(cr, SUPERUSER_ID, {})
    dependencies = ['hr']
    try:
        _logger.warning('Update dependencies')
        env['ir.module.module'].search(
            [('name', 'in', dependencies)]).write({'state': 'to upgrade'})
    except ValueError as e:
        _logger.warning(e)
    return
