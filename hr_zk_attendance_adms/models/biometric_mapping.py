# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError

class BiometricUserMapping(models.Model):
    """Modelo persistente para mapeo y administración de usuarios en dispositivos biométricos."""
    _name = 'biometric.user.mapping'
    _description = 'Biometric User Mapping'
    _order = 'status desc, cast_pin asc, id asc'

    device_user_id = fields.Char(string='ID Biométrico / PIN', required=True, index=True)
    device_user_name = fields.Char(string='Nombre en Biométrico')
    employee_id = fields.Many2one('hr.employee', string='Empleado de Odoo')
    status = fields.Selection([
        ('mapped', 'Mapeado (OK)'),
        ('unmapped', 'Sin Mapear (FALTA)'),
    ], string='Estado', default='unmapped', index=True)
    device_id = fields.Many2one('biometric.device.details', string='Dispositivo Fuente', required=True, ondelete='cascade', index=True)
    cast_pin = fields.Integer(string='PIN Numérico', compute='_compute_cast_pin', store=True, index=True)

    @api.depends('device_user_id')
    def _compute_cast_pin(self):
        for rec in self:
            try:
                rec.cast_pin = int(rec.device_user_id) if rec.device_user_id and rec.device_user_id.isdigit() else 999999999
            except Exception:
                rec.cast_pin = 999999999

    @api.model
    def is_name_compatible(self, name_device, name_odoo):
        """
        Determina si el nombre proveniente del biométrico es compatible con el nombre del empleado en Odoo.
        Evita falsos positivos como vincular 'carlos zamora' con 'JAVIER HERNAN TRANA PEREZ'.
        """
        if not name_device or not name_odoo:
            return False

        nd_clean = str(name_device).strip()
        no_clean = str(name_odoo).strip()
        if not nd_clean or not no_clean:
            return False
        if nd_clean.lower().startswith('usuario') or nd_clean.lower() == 'n/a':
            return False

        import unicodedata
        import re

        def _clean_str(s):
            s_norm = unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('utf-8').lower()
            return re.sub(r'[^a-z0-9]', '', s_norm)

        def _get_tokens(s):
            s_norm = unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('utf-8').lower()
            return {t for t in re.findall(r'[a-z0-9]+', s_norm) if len(t) > 1}

        c_str = _clean_str(nd_clean)
        o_str = _clean_str(no_clean)

        # 1. Coincidencia idéntica (ej. 'JAVIERFORERO' vs 'Javier Forero', 'CAMILA PAZ' vs 'Camila Paz')
        if c_str == o_str:
            return True

        # 2. Inclusión total si uno contiene al otro y tiene longitud suficiente (ej. 'Javier Forero' en 'Javier Forero Gomez')
        if len(c_str) >= 5 and len(o_str) >= 5:
            if c_str in o_str or o_str in c_str:
                return True

        # 3. Coincidencia por tokens/palabras
        c_tokens = _get_tokens(nd_clean)
        o_tokens = _get_tokens(no_clean)
        if not c_tokens or not o_tokens:
            return False

        common = c_tokens.intersection(o_tokens)
        # Si comparten al menos 2 palabras (ej. 'JAVIER HERNAN TRANA PEREZ' vs 'Javier Trana Perez')
        if len(common) >= 2:
            return True

        # Si uno de los dos nombres consta de solo 1 palabra y coincide exactamente (ej. 'GORIA')
        if len(common) == 1 and (len(c_tokens) == 1 and len(o_tokens) == 1):
            return True

        return False

    def write(self, vals):
        result = super().write(vals)
        if 'employee_id' in vals:
            for rec in self:
                if rec.employee_id:
                    # Liberar el PIN si otro empleado previo lo tenía por error
                    conflicting = self.env['hr.employee'].search([
                        ('device_id_num', '=', rec.device_user_id),
                        ('id', '!=', rec.employee_id.id)
                    ])
                    for old_emp in conflicting:
                        old_emp.with_context(skip_biometric_sync=True).write({'device_id_num': False})

                    rec.employee_id.with_context(skip_biometric_sync=True).write({'device_id_num': rec.device_user_id})
                    if rec.status != 'mapped':
                        super(BiometricUserMapping, rec).write({'status': 'mapped'})
                else:
                    if rec.status != 'unmapped':
                        super(BiometricUserMapping, rec).write({'status': 'unmapped'})
        return result

    def action_create_employee(self):
        """Crea un nuevo empleado en Odoo a partir de los datos del biométrico."""
        self.ensure_one()
        if self.employee_id:
            raise UserError(_("Este registro ya tiene un empleado asignado."))

        emp_name = self.device_user_name
        if not emp_name or emp_name.startswith("Usuario en Reloj") or emp_name == _("N/A"):
            emp_name = f"Empleado {self.device_user_id}"

        # Liberar PIN si estaba asignado a otro empleado
        conflicting = self.env['hr.employee'].search([
            ('device_id_num', '=', self.device_user_id)
        ])
        for old_emp in conflicting:
            old_emp.with_context(skip_biometric_sync=True).write({'device_id_num': False})

        emp = self.env['hr.employee'].with_context(skip_biometric_sync=True).create({
            'name': emp_name,
            'device_id_num': self.device_user_id,
        })
        self.write({
            'employee_id': emp.id,
            'status': 'mapped'
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Empleado %s creado y vinculado exitosamente.') % emp.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_auto_map_by_biometric_id(self):
        """Busca empleados en Odoo con el mismo ID Biométrico (device_id_num) y los vincula automáticamente.
        Por ningún motivo vincula por nombre."""
        device_id = self.env.context.get('default_device_id') or (self[0].device_id.id if self else False)
        domain = [('status', '=', 'unmapped')]
        if device_id:
            domain.append(('device_id', '=', device_id))
        unmapped = self.search(domain)
        count = 0
        Employee = self.env['hr.employee']
        for rec in unmapped:
            pin = (rec.device_user_id or '').strip()
            if pin:
                emp = Employee.search([('device_id_num', '=', pin)], limit=1)
                if emp:
                    rec.write({
                        'employee_id': emp.id,
                        'status': 'mapped'
                    })
                    count += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%d empleado(s) vinculados automáticamente por ID Biométrico.') % count,
                'type': 'success' if count else 'info',
                'sticky': False,
            }
        }

    def action_create_all_unmapped_employees(self):
        """Crea empleados en Odoo para todos los registros sin mapear."""
        device_id = self.env.context.get('default_device_id') or (self[0].device_id.id if self else False)
        domain = [('status', '=', 'unmapped')]
        if device_id:
            domain.append(('device_id', '=', device_id))
        unmapped = self.search(domain)
        count = 0
        Employee = self.env['hr.employee']
        for rec in unmapped:
            emp_name = rec.device_user_name
            if not emp_name or emp_name.startswith("Usuario en Reloj") or emp_name == _("N/A"):
                emp_name = f"Empleado {rec.device_user_id}"

            # Liberar PIN si estaba asignado a otro empleado
            conflicting = Employee.search([('device_id_num', '=', rec.device_user_id)])
            for old_emp in conflicting:
                old_emp.with_context(skip_biometric_sync=True).write({'device_id_num': False})

            emp = Employee.with_context(skip_biometric_sync=True).create({
                'name': emp_name,
                'device_id_num': rec.device_user_id,
            })
            rec.write({
                'employee_id': emp.id,
                'status': 'mapped'
            })
            count += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%d empleado(s) creados en Odoo exitosamente.') % count,
                'type': 'success' if count else 'info',
                'sticky': False,
            }
        }

    def action_delete_user_from_device(self):
        self.ensure_one()
        if not self.device_id:
            raise UserError(_("No hay dispositivo asociado."))

        dev = self.device_id
        pin = self.device_user_id

        if dev.protocol_type == 'pull':
            try:
                zk = dev._get_zk_connection(timeout=15)
                conn = dev.device_connect(zk)
                if not conn:
                    raise UserError(_("No se pudo conectar al dispositivo biométrico Pull."))
                users = conn.get_users()
                target_uid = None
                for u in users or []:
                    if str(u.user_id) == str(pin):
                        target_uid = u.uid
                        break
                if target_uid:
                    conn.delete_user(uid=target_uid)
                conn.disconnect()
            except Exception as e:
                raise UserError(_("Error al eliminar usuario en biométrico Pull: %s") % e)
            msg = _("Usuario %s eliminado correctamente del biométrico Pull.") % pin
        else:
            # En ADMS encolamos el comando DATA DELETE user
            cmd_str = f"DATA DELETE user Pin={pin}"
            self.env['biometric.device.command'].create({
                'device_id': dev.id,
                'command': cmd_str,
                'state': 'draft'
            })
            msg = _("Comando de eliminación para usuario %s encolado para el biométrico ADMS.") % pin

        self.unlink()
        return dev._display_notification(msg, 'success', True)

    def action_refresh_device_users(self):
        """Refresca la lista de usuarios directamente desde el biométrico y recarga la vista."""
        device_id = self.env.context.get('default_device_id') or (self[0].device_id.id if self else False)
        if not device_id:
            raise UserError(_("No se pudo identificar el dispositivo asociado."))
        device = self.env['biometric.device.details'].browse(device_id)
        return device.action_open_user_mapping_wizard()
