from odoo import fields, models, api
from odoo.exceptions import ValidationError

class PurchaseApprovalSetting(models.Model):
    _inherit = 'purchase.approval.setting'
    
    user_approvals_by_budget_am = fields.Many2many(
        comodel_name='res.users',
        relation='purchase_setting_am_user_rel',
        column1='setting_id',
        column2='user_id',
        string='Aprobadores por falta de presupuesto'
    )
    
    