from odoo import fields, models, api, _
from odoo.http import request

class ir_ui_menu(models.Model):
    _inherit = 'ir.ui.menu'

    def _get_access_management_hidden_menu_ids(self):
        """Ids de ir.ui.menu ocultados por reglas de Access Management para el
        usuario actual, respetando el filtro de compañía."""
        user = self.env.user
        if not user or user._is_public():
            return set()
        try:
            cid = request.httprequest.cookies.get('cids') and int(
                request.httprequest.cookies.get('cids').split('-')[0])
        except Exception:
            cid = False
        if not cid:
            cid = self.env.company.id
        rules = user.sudo().access_management_ids.filtered(
            lambda line: line.is_apply_on_without_company or cid in line.company_ids.ids)
        return set(rules.mapped('hide_menu_ids.menu_id'))

    @api.model
    def _visible_menu_ids(self, debug=False):
        """En 19 el árbol de menús del webclient se construye con `load_menus`
        /`get_user_roots` a través de `_visible_menu_ids` (que usa search_fetch,
        no `search`). Aquí quitamos los menús ocultados por Access Management
        para que se oculten tanto Apps (módulos) como submenús (modelos)."""
        visible = set(super()._visible_menu_ids(debug=debug))
        try:
            visible -= self._get_access_management_hidden_menu_ids()
        except Exception:
            pass
        return frozenset(visible)

    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        ids = super(ir_ui_menu, self).search(domain, offset=0, limit=None, order=order)
        all_menu =ids.ids
        # user = self.env.user
        # # user.clear_caches()
        # self.env['ir.ui.view'].sudo().clear_caches()
        # request.registry.clear_cache()
        # self.sudo().clear_caches()
        try:
            cids = request.httprequest.cookies.get('cids') and request.httprequest.cookies.get('cids').split('-')[0] or self.env.company.id
            for menu_id in self.env.user.access_management_ids.filtered(lambda line: line.is_apply_on_without_company == True or int(cids) in line.company_ids.ids).mapped('hide_menu_ids.menu_id'):
                if menu_id in all_menu:
                    all_menu.remove(menu_id)
                # menu_id = self.browse(menu_id)
                # if menu_id in ids:
                #     ids = ids - menu_id
            # if offset:
            #     ids = ids[offset:]
            # if limit:
            #     ids = ids[:limit]
        except:
            pass
        return self.browse(all_menu)
        # return len(ids) if count else ids
    
    @api.model_create_multi
    def create(self, vals_list):
        res = super(ir_ui_menu, self).create(vals_list)
        menu_item_obj = self.env['menu.item'].sudo()
        for record in res:
            menu_item_obj.create({'name':record.display_name,'menu_id':record.id})
        return res
    
    def write(self, vals):
        res = super(ir_ui_menu, self).write(vals)
        menu_item_obj = self.env['menu.item'].sudo()
        for record in self:
            menu_item_obj.search([('menu_id','=',record.id)]).write({'name':record.display_name})
        return res
    
    def unlink(self):
        menu_item_obj = self.env['menu.item'].sudo()
        for record in self:
            menu_item_obj.search([('menu_id','=',record.id)]).unlink()
        return super(ir_ui_menu, self).unlink()

