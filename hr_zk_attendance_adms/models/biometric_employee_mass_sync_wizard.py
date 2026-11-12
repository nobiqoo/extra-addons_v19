# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BiometricEmployeeMassSyncWizard(models.TransientModel):
    _name = 'biometric.employee.mass.sync.wizard'
    _description = 'Wizard de Sincronización Masiva de Empleados a Biométricos'

    employee_ids = fields.Many2many(
        'hr.employee',
        'biometric_mass_sync_emp_rel',
        'wizard_id',
        'employee_id',
        string='Empleados Seleccionados',
        required=True
    )

    sync_mode = fields.Selection([
        ('by_config', 'Respetar configuración de cada empleado (Dispositivos Permitidos)'),
        ('force_devices', 'Forzar a los dispositivos seleccionados a continuación')
    ], string='Modo de Destino', default='by_config', required=True)

    device_ids = fields.Many2many(
        'biometric.device.details',
        'biometric_mass_sync_dev_rel',
        'wizard_id',
        'device_id',
        string='Dispositivos Específicos',
        domain="[('authorized', '=', True)]"
    )

    action_type = fields.Selection([
        ('enable', 'Cargar / Habilitar en biométricos (Disable=0)'),
        ('disable', 'Inhabilitar acceso temporal (Disable=1, conserva biometría)'),
        ('delete', 'Eliminar usuarios de los biométricos (DATA DELETE)')
    ], string='Acción', default='enable', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids')
        active_model = self.env.context.get('active_model')
        if active_ids and active_model == 'hr.employee':
            res['employee_ids'] = [(6, 0, active_ids)]
        auth_devices = self.env['biometric.device.details'].search([('authorized', '=', True)])
        res['device_ids'] = [(6, 0, auth_devices.ids)]
        return res

    def action_execute_sync(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_("No hay empleados seleccionados."))

        all_auth_devices = self.env['biometric.device.details'].search([('authorized', '=', True)])
        if not all_auth_devices:
            raise UserError(_("No hay dispositivos biométricos autorizados en el sistema."))

        if self.sync_mode == 'force_devices' and not self.device_ids:
            raise UserError(_("Debe seleccionar al menos un dispositivo biométrico."))

        count_synced = 0
        missing_id_count = 0

        for emp in self.employee_ids:
            if not emp.device_id_num:
                missing_id_count += 1
                continue

            if self.sync_mode == 'by_config':
                if self.action_type == 'enable':
                    emp._sync_biometric_user()
                    count_synced += 1
                elif self.action_type == 'disable':
                    target_devs = emp.allowed_device_ids.filtered(lambda d: d.authorized) if emp.allowed_device_ids else all_auth_devices
                    for dev in target_devs:
                        dev._enqueue_user_command(pin=emp.device_id_num, action='disable')
                    count_synced += 1
                elif self.action_type == 'delete':
                    emp._delete_biometric_user()
                    count_synced += 1
            else:
                for dev in self.device_ids:
                    dev._enqueue_user_command(
                        pin=emp.device_id_num,
                        name=emp.name,
                        action=self.action_type
                    )
                    if self.action_type == 'enable' and emp.has_custom_profile_image():
                        dev._enqueue_user_photo(pin=emp.device_id_num, image_data=emp.image_1920)
                count_synced += 1

        action_labels = {
            'enable': _('habilitados/cargados'),
            'disable': _('inhabilitados'),
            'delete': _('eliminados')
        }
        msg = _('Sincronización procesada: %d empleados %s.') % (
            count_synced,
            action_labels.get(self.action_type, self.action_type)
        )
        if missing_id_count:
            msg += _(' (%d empleados omitidos por no tener ID Biométrico).') % missing_id_count

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': msg,
                'type': 'success' if count_synced else 'warning',
                'sticky': False,
            }
        }
