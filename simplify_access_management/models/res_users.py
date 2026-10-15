from odoo import fields, models, api, SUPERUSER_ID,_
from odoo.exceptions import UserError, AccessDenied
from .query_prepare import search_data
import logging
_logger = logging.getLogger(__name__)

class res_users(models.Model):
    _inherit = 'res.users'

    access_management_ids = fields.Many2many('access.management', 'access_management_users_rel_ah', 'user_id', 'access_management_id', 'Access Pack')
    
    def write(self, vals):
        res = super(res_users, self).write(vals)
        for user in self:
            for access in user.sudo().access_management_ids:
                if user.env.company in access.company_ids and access.readonly:
                    if user.has_group('base.group_system') or user.has_group('base.group_erp_manager'):
                        raise UserError(_('Admin user can not be set as a read-only..!'))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super(res_users, self).create(vals_list)
        for record in self:
            for access in record.sudo().access_management_ids:    
                if self.env.company in access.company_ids and access.readonly:
                    if record.has_group('base.group_system') or record.has_group('base.group_erp_manager'):
                        raise UserError(_('Admin user can not be set as a read-only..!'))
        return res


    def _login(self, credential, user_agent_env):
        res = super()._login(credential, user_agent_env=user_agent_env)
        try:
            uid = res.get('uid')
            if uid:
                self_user = self.env(user=uid)[self._name]
                result = search_data(self_user, 'access.management', condition=('disable_login','=',True), operator='AND', limit=1)
                if result:
                    raise AccessDenied("Login is disabled for this user due to access management settings.")
        except AccessDenied:
            _logger.info("Login failed for login:%s", credential.get('login'))
            raise
        return res

    # remove archive action with rules
    @api.model
    def get_user_info_for_archived_rules(self, ids):
        if not ids:
            return []
        access_data = self.env['access.management'].sudo().with_context(active_test=False)
        res = []
        users = self.sudo().browse(ids)
        for user in users:
            access_recs = access_data.search([('user_ids', 'in', user.id)])
            rules = [a.name for a in access_recs]
            res.append({'user_id': user.id, 'display_name': user.name or user.login, 'rules': rules})
        return res
        
    # action archive override
    def action_archive(self):
        res = super(res_users, self).action_archive()
        access_data = self.env['access.management'].sudo().with_context(active_test=False)
        for user in self:
            access_recs = access_data.search([('user_ids', 'in', user.id)])
            for a in access_recs:
                a.sudo().write({'user_ids': [(3, user.id)]})
        return res


