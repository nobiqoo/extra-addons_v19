from odoo import api, fields, models


class menu_item(models.Model):
    _name = 'menu.item'
    _description = "Menu Item"

    name = fields.Char('Menu')
    menu_id = fields.Integer('Menu ID')

    def _compute_display_name(self):
        lang = self.env.context.get('lang') or self.env.user.lang
        menu_ids = [r.menu_id for r in self if r.menu_id]
        if menu_ids:
            all_menus = self.env['ir.ui.menu'].with_context(lang=lang).browse(menu_ids)
            ancestor_ids = set(menu_ids)
            batch = all_menus
            while batch:
                parents = batch.filtered('parent_id').mapped('parent_id')
                new_ids = set(parents.ids) - ancestor_ids
                if not new_ids:
                    break
                ancestor_ids |= new_ids
                batch = self.env['ir.ui.menu'].with_context(lang=lang).browse(list(new_ids))
            all_ancestors = self.env['ir.ui.menu'].with_context(lang=lang).browse(list(ancestor_ids))
            parent_map = {m.id: (m.parent_id.id or None) for m in all_ancestors}
            name_map = {m.id: m.name or '' for m in all_ancestors}
        else:
            parent_map = {}
            name_map = {}

        for record in self:
            if not record.menu_id:
                record.display_name = record.name or ''
                continue
            parts = []
            current_id = record.menu_id
            visited = set()
            while current_id and current_id not in visited:
                visited.add(current_id)
                parts.insert(0, name_map.get(current_id, ''))
                current_id = parent_map.get(current_id)
            record.display_name = ' / '.join(p for p in parts if p) or record.name or ''