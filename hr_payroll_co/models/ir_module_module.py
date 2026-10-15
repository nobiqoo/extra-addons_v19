# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons import hr_payroll_co


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def hook_to_upgrade(self):
        hr_payroll_co.pre_init_hook(self.env)
        hr_payroll_co.post_init_hook(self.env)
