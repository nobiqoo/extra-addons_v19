# -*- coding: utf-8 -*-
import logging
from odoo import fields, models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    device_id_num = fields.Char(
        string='Biometric Device ID',
        help="Identificador del usuario en el dispositivo biométrico (PIN numérico)"
    )

    allowed_device_ids = fields.Many2many(
        'biometric.device.details',
        string='Dispositivos Permitidos',
        help="Si se selecciona, solo estos dispositivos específicos tendrán habilitado al usuario y procesarán sus marcaciones. Si está vacío, se habilita y sincroniza en todos los biométricos autorizados."
    )

    def has_custom_profile_image(self):
        """Retorna True si el empleado tiene una foto de perfil real personalizada (no el avatar SVG por defecto de Odoo)."""
        self.ensure_one()
        if not self.image_1920:
            return False
        import base64
        try:
            val = self.image_1920
            raw = base64.b64decode(val) if isinstance(val, (str, bytes)) else b''
            head = raw.strip()[:60].lower()
            if b'<?xml' in head or b'<svg' in head or b'<!doctype svg' in head:
                return False
            return len(raw) > 100
        except Exception:
            return False

    def _get_target_biometric_devices(self):
        """Retorna (target_devices, disabled_devices) según allowed_device_ids y dispositivos autorizados."""
        self.ensure_one()
        all_auth_devices = self.env['biometric.device.details'].search([('authorized', '=', True)])
        if self.allowed_device_ids:
            target = self.allowed_device_ids.filtered(lambda d: d.authorized)
            disabled = all_auth_devices - target
        else:
            target = all_auth_devices
            disabled = self.env['biometric.device.details']
        return target, disabled

    def _sync_biometric_user(self):
        """Sincroniza el usuario y su foto facial según la Opción C (Comportamiento Inteligente Mixto)."""
        self.ensure_one()
        if not self.device_id_num or not self.active:
            return

        target_devices, disabled_devices = self._get_target_biometric_devices()

        # 1. Habilitar / Actualizar en dispositivos permitidos
        for dev in target_devices:
            dev._enqueue_user_command(pin=self.device_id_num, name=self.name, action='enable')
            # Si tiene foto real personalizada, sincronizar biophoto
            if self.has_custom_profile_image():
                dev._enqueue_user_photo(pin=self.device_id_num, image_data=self.image_1920)

        # 2. Inhabilitar en dispositivos excluidos/retirados (Disable=1, conserva biometría en el reloj)
        for dev in disabled_devices:
            dev._enqueue_user_command(pin=self.device_id_num, name=self.name, action='disable')

    def _delete_biometric_user(self, pin=None):
        """Elimina el usuario por completo de todos los biométricos autorizados (al archivar o eliminar)."""
        self.ensure_one()
        target_pin = pin or self.device_id_num
        if not target_pin:
            return
        all_auth_devices = self.env['biometric.device.details'].search([('authorized', '=', True)])
        for dev in all_auth_devices:
            dev._enqueue_user_command(pin=target_pin, action='delete')

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        if self.env.context.get('skip_biometric_sync'):
            return employees

        for emp in employees:
            if emp.active and emp.device_id_num:
                try:
                    emp._sync_biometric_user()
                except Exception as e:
                    _logger.error("Error sincronizando empleado %s a biometricos al crear: %s", emp.name, e)
        return employees

    def write(self, vals):
        if self.env.context.get('skip_biometric_sync'):
            return super().write(vals)

        # Capturar estado previo
        pins_before = {emp.id: emp.device_id_num for emp in self}
        active_before = {emp.id: emp.active for emp in self}

        res = super().write(vals)

        relevant_fields = {'device_id_num', 'name', 'active', 'allowed_device_ids', 'image_1920'}
        if not (relevant_fields & set(vals.keys())):
            return res

        for emp in self:
            old_pin = pins_before.get(emp.id)

            # Caso 1: Empleado archivado o desactivado -> Eliminación total de relojes
            if 'active' in vals and not emp.active:
                if old_pin:
                    emp._delete_biometric_user(pin=old_pin)
                continue

            # Caso 2: Empleado activo
            if emp.active:
                # Si cambió el PIN, eliminar el PIN anterior
                if 'device_id_num' in vals and old_pin and old_pin != emp.device_id_num:
                    emp._delete_biometric_user(pin=old_pin)

                # Si cambió la foto de perfil y es personalizada, enviarla a los dispositivos
                if 'image_1920' in vals and emp.device_id_num and emp.has_custom_profile_image():
                    target_devs, _ = emp._get_target_biometric_devices()
                    for dev in target_devs:
                        dev._enqueue_user_photo(pin=emp.device_id_num, image_data=emp.image_1920)

                # Sincronizar nuevo estado/dispositivos
                if any(k in vals for k in ('device_id_num', 'name', 'active', 'allowed_device_ids')):
                    if emp.device_id_num:
                        try:
                            emp._sync_biometric_user()
                        except Exception as e:
                            _logger.error("Error sincronizando empleado %s a biometricos: %s", emp.name, e)

        return res

    def unlink(self):
        if not self.env.context.get('skip_biometric_sync'):
            for emp in self:
                if emp.device_id_num:
                    try:
                        emp._delete_biometric_user()
                    except Exception as e:
                        _logger.error("Error eliminando usuario de biométricos al borrar empleado: %s", e)
        return super().unlink()

    def action_sync_to_biometrics(self):
        """Acción de botón manual para forzar sincronización del empleado con sus biométricos."""
        for emp in self:
            if not emp.device_id_num:
                raise UserError(_("El empleado %s no tiene asignado un ID Biométrico.") % emp.name)
            emp._sync_biometric_user()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Comandos de sincronización de usuario y foto facial encolados correctamente para los biométricos.'),
                'type': 'success',
                'sticky': False,
            }
        }
