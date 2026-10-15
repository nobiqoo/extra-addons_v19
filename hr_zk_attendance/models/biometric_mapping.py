# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError

class BiometricUserMapping(models.TransientModel):
    """Modelo temporal para mostrar la comparación de usuarios entre el dispositivo y Odoo."""
    _name = 'biometric.user.mapping'
    _description = 'Biometric User Mapping Report'

    device_user_id = fields.Char(string='ID del Dispositivo', readonly=True)
    device_user_name = fields.Char(string='Nombre en Biometrico', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado de Odoo')
    status = fields.Selection([
        ('mapped', 'Mapeado (OK)'),
        ('unmapped', 'Sin Mapear (FALTA)'),
    ], string='Estado', readonly=True)
    device_id = fields.Many2one('biometric.device.details', string='Dispositivo Fuente', readonly=True)

    def write(self, vals):
        result = super().write(vals)
        if vals.get('employee_id'):
            for mapping_record in self:
                mapping_record.employee_id.write({'device_id_num': mapping_record.device_user_id})
        return result

    def action_delete_user_from_device(self):
        self.ensure_one()
        try:
            zk = self.device_id._get_zk_connection(timeout=15)
            conn = zk.connect()
            users = conn.get_users()

            target_uid = None
            target_user_id = None
            target_name = None

            # Buscar coincidencia por user_id
            for u in users:
                if str(u.user_id) == str(self.device_user_id):
                    target_uid = u.uid
                    target_user_id = u.user_id
                    target_name = u.name
                    break

            if not target_uid:
                conn.disconnect()
                raise UserError(_('Usuario no encontrado en el dispositivo.'))

            # Intentar eliminar usando UID
            conn.delete_user(uid=target_uid)

            # Verificar si sigue en la lista
            users_after = conn.get_users()
            still_exists = any(str(u.user_id) == str(self.device_user_id) for u in users_after)

            if still_exists:
                # Workaround: actualizar user_id a uno corto y eliminar
                new_id = "9999"
                conn.set_user(uid=target_uid, name=target_name, privilege=0, password="", group_id="", user_id=new_id)
                conn.delete_user(uid=target_uid)
                msg = _('Usuario con ID largo actualizado a %s y eliminado.') % new_id
            else:
                msg = _('Usuario eliminado correctamente.')

            conn.disconnect()

            # Mostrar notificación y recargar wizard
            self.device_id._display_notification(msg, 'success', True)

            return {
                'type': 'ir.actions.client',
                'tag': 'reload'
            }
        except Exception as e:
            raise UserError(_('Error al eliminar usuario: %s') % str(e))