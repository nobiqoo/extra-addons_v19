from . import models
# from . import wizard
from . import controllers


from odoo import api, SUPERUSER_ID


def uninstall_hook(env):
    env['ir.config_parameter'].search([('key', '=', 'uninstall_check')]).unlink()


def _rebuild_menu_item_names(env):
    """Update menu.item names using the primary non-English language."""
    for code in ('es_CO', 'es_MX', 'es_AR', 'es'):
        if env['res.lang'].search([('code', '=', code), ('active', '=', True)], limit=1):
            lang = code
            break
    else:
        other = env['res.lang'].search([('active', '=', True), ('code', '!=', 'en_US')], limit=1)
        lang = other.code if other else 'en_US'

    all_menus = env['ir.ui.menu'].with_context(lang=lang).search([])
    parent_map = {m.id: (m.parent_id.id or None) for m in all_menus}
    name_map = {m.id: m.name or '' for m in all_menus}

    for item in env['menu.item'].search([]):
        if not item.menu_id:
            continue
        parts = []
        current_id = item.menu_id
        visited = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            parts.insert(0, name_map.get(current_id, ''))
            current_id = parent_map.get(current_id)
        translated_name = ' / '.join(p for p in parts if p)
        if translated_name:
            item.write({'name': translated_name})


def post_install_action_dup_hook(env):
    action_data_obj = env['action.data']
    menu_item_obj = env['menu.item']
    for action in env['ir.actions.actions'].search([]):
        action_data_obj.create({'name': action.name, 'action_id': action.id})
    for menu in env['ir.ui.menu'].search([]):
        menu_item_obj.create({'name': menu.display_name, 'menu_id': menu.id})
    _rebuild_menu_item_names(env)
