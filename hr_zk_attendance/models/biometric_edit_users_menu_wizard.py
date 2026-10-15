# -*- coding: utf-8 -*-
from odoo import models, api, _

class BiometricEditUsersMenuWizard(models.TransientModel):
    _name = 'biometric.edit.users.menu.wizard'
    _description = 'Menú de edición de usuarios biométricos'

    def action_map_biometric_to_odoo(self):
        device = self.env['biometric.device.details'].browse(self.env.context.get('active_id'))
        return device.action_open_user_mapping_wizard()

    def action_map_odoo_to_biometric(self):
        device = self.env['biometric.device.details'].browse(self.env.context.get('active_id'))
        return device.action_open_odoo_to_biometric_wizard()