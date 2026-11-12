# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BiometricOdooToBiometricWizard(models.TransientModel):
    _name = 'biometric.odoo.to.biometric.wizard'
    _description = 'Wizard para cargar/sincronizar usuarios de Odoo a Biométricos'

    device_ids = fields.Many2many(
        'biometric.device.details',
        'biometric_adms_wizard_dev_rel',
        'wizard_id',
        'device_id',
        string='Dispositivos Biométricos',
        domain="[('authorized', '=', True)]",
        required=True
    )

    device_id = fields.Many2one(
        'biometric.device.details',
        string='Dispositivo',
        domain="[('authorized', '=', True)]"
    )

    sync_action = fields.Selection([
        ('enable', 'Cargar / Habilitar usuarios (Disable=0)'),
        ('disable', 'Inhabilitar acceso temporal (Disable=1, conserva biometría)'),
        ('delete', 'Eliminar usuarios del biométrico (DATA DELETE)')
    ], string='Acción a Realizar', default='enable', required=True)

    employee_ids = fields.Many2many(
        'hr.employee',
        'biometric_adms_wizard_emp_rel',
        'wizard_id',
        'employee_id',
        string='Empleados con Biometric ID'
    )

    employee_ids_without_id = fields.Many2many(
        'hr.employee',
        'biometric_adms_wizard_emp_noid_rel',
        'wizard_id',
        'employee_id',
        string='Empleados sin Biometric ID'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')

        # Si viene desde un biométrico específico
        if active_id and active_model == 'biometric.device.details':
            res['device_id'] = active_id
            res['device_ids'] = [(6, 0, [active_id])]
        elif self.env.context.get('default_device_ids'):
            res['device_ids'] = [(6, 0, self.env.context.get('default_device_ids'))]
        else:
            auth_devices = self.env['biometric.device.details'].search([('authorized', '=', True)])
            res['device_ids'] = [(6, 0, auth_devices.ids)]
            if auth_devices:
                res['device_id'] = auth_devices[0].id

        if 'employee_ids' in fields_list and not res.get('employee_ids'):
            emps_with_id = self.env['hr.employee'].search([
                ('device_id_num', '!=', False),
                ('active', '=', True)
            ])
            res['employee_ids'] = [(6, 0, emps_with_id.ids)]

        if 'employee_ids_without_id' in fields_list and not res.get('employee_ids_without_id'):
            emps_without_id = self.env['hr.employee'].search([
                ('device_id_num', '=', False),
                ('active', '=', True)
            ])
            res['employee_ids_without_id'] = [(6, 0, emps_without_id.ids)]

        return res

    def action_save_biometric_id(self):
        for emp in self.employee_ids_without_id:
            if not emp.device_id_num:
                raise UserError(_('Debe asignar un Biometric ID a todos los empleados de la lista antes de guardar.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('IDs biométricos guardados correctamente.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_upload_users(self):
        self.ensure_one()
        devices = self.device_ids
        if not devices and self.device_id:
            devices = self.device_id
        if not devices:
            raise UserError(_('Debe seleccionar al menos un dispositivo biométrico.'))

        if not self.employee_ids:
            raise UserError(_('Debe seleccionar al menos un empleado para sincronizar.'))

        count_queued = 0
        missing_ids = []

        for emp in self.employee_ids:
            if not emp.device_id_num:
                missing_ids.append(emp.name)
                continue

            for dev in devices:
                if dev.protocol_type == 'pull':
                    try:
                        zk = dev._get_zk_connection(timeout=15)
                        conn = dev.device_connect(zk)
                        if conn:
                            existing_users = conn.get_users() or []
                            existing_uids = [u.uid for u in existing_users]
                            next_uid = max(existing_uids) + 1 if existing_uids else 1
                            if self.sync_action == 'enable':
                                conn.set_user(
                                    uid=next_uid,
                                    name=emp.name,
                                    privilege=0,
                                    password='',
                                    group_id='',
                                    user_id=str(emp.device_id_num)
                                )
                            elif self.sync_action == 'delete':
                                for u in existing_users:
                                    if str(u.user_id) == str(emp.device_id_num):
                                        conn.delete_user(uid=u.uid)
                                        break
                            conn.disconnect()
                            count_queued += 1
                    except Exception as e:
                        _logger.error("Error subiendo usuario a biométrico Pull: %s", e)
                else:
                    dev._enqueue_user_command(
                        pin=emp.device_id_num,
                        name=emp.name,
                        action=self.sync_action
                    )
                    if self.sync_action == 'enable' and emp.has_custom_profile_image():
                        dev._enqueue_user_photo(pin=emp.device_id_num, image_data=emp.image_1920)
                    count_queued += 1

        action_labels = {
            'enable': _('habilitar/cargar'),
            'disable': _('inhabilitar'),
            'delete': _('eliminar')
        }
        msg = _('Se encolaron %d órdenes de usuario (%s) en %d dispositivo(s).') % (
            count_queued,
            action_labels.get(self.sync_action, self.sync_action),
            len(devices)
        )
        if missing_ids:
            msg += _('\nOmitidos sin ID: %s') % ', '.join(missing_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': msg,
                'type': 'success',
                'sticky': False,
            }
        }
