# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BiometricOdooToBiometricWizard(models.TransientModel):
    _name = 'biometric.odoo.to.biometric.wizard'
    _description = 'Wizard para cargar usuarios de Odoo al biométrico'

    device_id = fields.Many2one('biometric.device.details', string='Dispositivo', required=True)

    employee_ids = fields.Many2many(
        'hr.employee',
        'biometric_wizard_employee_rel',
        'wizard_id',
        'employee_id',
        string='Empleados con Biometric ID'
    )

    employee_ids_without_id = fields.Many2many(
        'hr.employee',
        'biometric_wizard_employee_noid_rel',
        'wizard_id',
        'employee_id',
        string='Empleados sin Biometric ID'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
             res['device_id'] = self.env.context.get('active_id')
        return res

    def action_save_biometric_id(self):
        for emp in self.employee_ids_without_id:
            if not emp.device_id_num:
                raise UserError(_('Debe asignar un Biometric ID a todos los empleados antes de cargar.'))
        return True

    
    def action_upload_users(self):
        device = self.device_id
        uploaded = []
        errors = []
        try:
            zk = device._get_zk_connection(timeout=15)
            conn = zk.connect()

            # Obtener el siguiente UID disponible (valor interno del dispositivo)
            existing_uids = [u.uid for u in conn.get_users()]
            next_uid = max(existing_uids) + 1 if existing_uids else 1

            for emp in self.employee_ids:
                if not emp.device_id_num:
                    errors.append(emp.name)
                    continue
                try:
                    # Crear usuario con UID válido y Biometric ID como user_id
                    conn.set_user(
                        uid=next_uid,  # UID interno válido
                        name=emp.name,
                        privilege=0,
                        password='',
                        group_id='',
                        user_id=str(emp.device_id_num)  # Biometric ID como user_id
                    )
                    uploaded.append(emp.name)
                    next_uid += 1  # Incrementar para el siguiente usuario
                except Exception as e:
                    errors.append('%s (%s)' % (emp.name, str(e)))

            conn.disconnect()
        except Exception as e:
            raise UserError(_('Error conectando al dispositivo: %s') % str(e))

        msg = _('Usuarios cargados: %s\nErrores: %s') % (
            ', '.join(uploaded) if uploaded else '0',
            ', '.join(errors) if errors else '0'
        )
        return device._display_notification(msg, 'info', True)
