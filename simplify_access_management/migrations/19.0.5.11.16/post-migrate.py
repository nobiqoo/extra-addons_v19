from odoo import api, SUPERUSER_ID


def _get_primary_lang(env):
    for code in ('es_CO', 'es_MX', 'es_AR', 'es'):
        if env['res.lang'].search([('code', '=', code), ('active', '=', True)], limit=1):
            return code
    lang = env['res.lang'].search([('active', '=', True), ('code', '!=', 'en_US')], limit=1)
    return lang.code if lang else 'en_US'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lang = _get_primary_lang(env)

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
