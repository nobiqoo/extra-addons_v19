# -*- coding: utf-8 -*-
import logging
import pytz
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

def optimize_biophoto(image_data):
    """
    Optimiza una foto (bytes o base64) para terminales ZKTeco SpeedFace (Visible Light).
    - Descarta avatares SVG genéricos de Odoo.
    - Convierte a RGB (descarta canal Alpha PNG y perfiles CMYK).
    - Reescalado proporcional a máx 480x640 px (resolución óptica nativa).
    - Compresión JPEG calidad 85 (peso óptimo: ~35-60 KB).
    - Retorna tuple: (bin_size_en_bytes, clean_b64_str) o None si inválida.
    """
    if not image_data:
        return None
    import io
    import base64
    from PIL import Image

    # Limpiar y obtener bytes crudos
    if isinstance(image_data, str):
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        clean_b64 = image_data.replace('\n', '').replace('\r', '').strip()
        try:
            raw_bytes = base64.b64decode(clean_b64)
        except Exception:
            return None
    elif isinstance(image_data, bytes):
        try:
            if image_data.strip().startswith(b'/9j/') or image_data.strip().startswith(b'iVBOR') or image_data.strip().startswith(b'PD94'):
                raw_bytes = base64.b64decode(image_data)
            else:
                try:
                    raw_bytes = base64.b64decode(image_data)
                except Exception:
                    raw_bytes = image_data
        except Exception:
            raw_bytes = image_data
    else:
        return None

    if not raw_bytes or len(raw_bytes) < 100:
        return None

    # Descartar avatares SVG genéricos de Odoo
    head = raw_bytes.strip()[:60].lower()
    if b'<?xml' in head or b'<svg' in head or b'<!doctype svg' in head:
        return None

    try:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        if img.width > 480 or img.height > 640:
            img.thumbnail((480, 640), Image.Resampling.LANCZOS)
        out_io = io.BytesIO()
        img.save(out_io, format='JPEG', quality=85, optimize=True)
        opt_bytes = out_io.getvalue()
        return len(opt_bytes), base64.b64encode(opt_bytes).decode('ascii')
    except Exception as e:
        _logger.warning("Error optimizando biophoto con PIL: %s", e)
        return None

class BiometricDeviceDetails(models.Model):
    _name = 'biometric.device.details'
    _description = 'Biometric Device Details (ADMS Push & Pull)'
    _order = 'name asc'

    # ----------------------------------------------------
    # FIELDS
    # ----------------------------------------------------
    name = fields.Char(string='Nombre', required=True, help='Nombre descriptivo del biométrico')
    sn = fields.Char(
        string='Número de Serie (SN)',
        index=True,
        copy=False,
        help="Número de serie exacto reportado por el dispositivo ZKTeco (visible en Menú -> Información del Sistema)."
    )
    protocol_type = fields.Selection([
        ('adms', 'Nube / ADMS (SpeedFace PUSH)'),
        ('pull', 'Red Local / Pull (Standalone pyzk)'),
    ], string='Tipo de Comunicación', default='adms', required=True,
       help="ADMS: El dispositivo empuja datos a Odoo por HTTP. Pull: Odoo se conecta a la IP/puerto del biométrico.")
    device_ip = fields.Char(string='Device IP', help="IP del biométrico (para Pull) o última IP conocida (para ADMS)")
    port_number = fields.Integer(string='Port Number', default=4370)
    address_id = fields.Many2one('res.partner', string='Working Address')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True
    )
    
    device_timezone = fields.Selection(
        '_get_timezones',
        string='Device Timezone',
        default='America/Bogota',
        required=True,
        help="Zona horaria donde se encuentra físicamente el reloj. Convierte las horas locales a UTC en Odoo."
    )

    last_sync_at = fields.Datetime(string='Última Sincronización', readonly=True)
    last_heartbeat = fields.Datetime(string='Último Latido (Heartbeat)', readonly=True)
    
    status = fields.Selection([
        ('idle', 'Idle'),
        ('ok', 'OK'),
        ('error', 'Error'),
        ('syncing', 'Syncing')
    ], default='idle', readonly=True)

    connection_state = fields.Selection([
        ('online', 'En Línea'),
        ('offline', 'Fuera de Línea')
    ], string='Estado Conexión', compute='_compute_connection_state', store=False)

    authorized = fields.Boolean(
        string='Autorizado',
        default=True,
        help="Si está marcado, Odoo procesa y guarda las marcaciones de este biométrico. Si está desmarcado, se reciben los latidos pero se descartan las marcaciones de forma segura."
    )

    last_error = fields.Text(string='Último Error', readonly=True)
    pull_fail_count = fields.Integer(string='Fallos Consecutivos (Pull)', default=0, readonly=True)
    pull_next_retry = fields.Datetime(string='Próximo Reintento (Pull)', readonly=True)

    command_ids = fields.One2many(
        'biometric.device.command',
        'device_id',
        string='Comandos Pendientes / Historial'
    )
    command_count = fields.Integer(
        string='Total Comandos',
        compute='_compute_command_count'
    )

    def _compute_command_count(self):
        for dev in self:
            dev.command_count = len(dev.command_ids)

    def action_view_commands(self):
        self.ensure_one()
        return {
            'name': _('Comandos ADMS - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.device.command',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    @api.constrains('sn')
    def _check_sn_unique(self):
        for rec in self:
            if rec.sn:
                dupes = self.search([('sn', '=', rec.sn), ('id', '!=', rec.id)])
                if dupes:
                    raise ValidationError(_('El Número de Serie (SN) %s ya está registrado en otro biométrico.') % rec.sn)

    @api.model
    def _get_timezones(self):
        return [(tz, tz) for tz in pytz.all_timezones]

    @api.depends('last_heartbeat', 'status', 'protocol_type')
    def _compute_connection_state(self):
        limit = fields.Datetime.now() - timedelta(minutes=5)
        for dev in self:
            if dev.protocol_type == 'adms':
                if dev.last_heartbeat and dev.last_heartbeat > limit:
                    dev.connection_state = 'online'
                else:
                    dev.connection_state = 'offline'
            else:
                dev.connection_state = 'online' if dev.status == 'ok' else 'offline'

    # ----------------------------------------------------
    # HELPERS
    # ----------------------------------------------------
    def _display_notification(self, message, type='info', sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': type,
                'sticky': sticky,
            },
        }

    def _get_zk_connection(self, timeout=20):
        self.ensure_one()
        try:
            from zk import ZK
        except ImportError:
            _logger.error("pyzk no está instalado (pip install pyzk).")
            return None

        return ZK(
            self.device_ip,
            port=self.port_number or 4370,
            timeout=timeout,
            password=0,
            force_udp=False,
            ommit_ping=False,
        )

    def device_connect(self, zk_obj):
        try:
            return zk_obj.connect()
        except Exception:
            return False

    def _test_connection_logic(self):
        self.ensure_one()
        try:
            zk = self._get_zk_connection(timeout=10)
            if zk:
                conn = self.device_connect(zk)
                if conn:
                    self.write({
                        'status': 'ok',
                        'last_error': False,
                    })
                    conn.disconnect()
                    return True, None
        except Exception as e:
            self.write({'status': 'error', 'last_error': str(e)})
            return False, str(e)
        self.write({'status': 'error', 'last_error': 'Conexión fallida'})
        return False, 'Conexión fallida'

    # ----------------------------------------------------
    # ACTIONS & BUTTONS
    # ----------------------------------------------------
    def action_test_connection(self):
        self.ensure_one()
        if self.protocol_type == 'adms':
            limit = fields.Datetime.now() - timedelta(minutes=5)
            if self.last_heartbeat and self.last_heartbeat > limit:
                self.write({'status': 'ok', 'last_error': False})
                return self._display_notification(
                    _('Dispositivo En Línea y comunicando activamente por ADMS.'), 'success'
                )
            else:
                msg = _('El dispositivo no ha reportado latidos en los últimos 5 minutos. Verifique en el reloj la configuración de Servidor en la Nube (ADMS).')
                self.write({'status': 'idle'})
                return self._display_notification(msg, 'warning')
        else:
            success, error_msg = self._test_connection_logic()
            if success:
                return self._display_notification(_('Conectado exitosamente al biométrico por Pull.'), 'success')
            else:
                raise ValidationError(error_msg)

    def action_set_timezone(self):
        self.ensure_one()
        tz_name = self.device_timezone or 'America/Bogota'
        try:
            dev_tz = pytz.timezone(tz_name)
        except Exception:
            dev_tz = pytz.UTC

        now_local = datetime.now(pytz.utc).astimezone(dev_tz)

        if self.protocol_type == 'pull':
            zk = self._get_zk_connection(timeout=10)
            conn = self.device_connect(zk)
            if conn:
                try:
                    conn.set_time(now_local.replace(tzinfo=None))
                    conn.disconnect()
                    return self._display_notification(_('Hora del dispositivo sincronizada a %s') % now_local.strftime('%Y-%m-%d %H:%M:%S'), 'success')
                except Exception as e:
                    raise UserError(str(e))
            raise UserError(_('No se pudo conectar al dispositivo'))
        else:
            cmd_str = f"SET TIME {now_local.strftime('%Y-%m-%d %H:%M:%S')}"
            self.env['biometric.device.command'].create({
                'device_id': self.id,
                'command': cmd_str,
                'state': 'draft'
            })
            return self._display_notification(
                _('Comando de sincronización de hora (%s) encolado para el biométrico.') % now_local.strftime('%Y-%m-%d %H:%M:%S'), 'success'
            )

    def action_download_attendance(self):
        for dev in self:
            if not dev.authorized:
                _logger.info("ADMS: Dispositivo %s no está autorizado para sincronizar marcaciones. Omitiendo.", dev.name)
                continue
            if dev.protocol_type == 'pull':
                dev._download_pull_attendance()
            else:
                dev.env['biometric.device.command'].create({
                    'device_id': dev.id,
                    'command': 'DATA QUERY ATTLOG',
                    'state': 'draft'
                })
        self._sync_to_hr_attendance()
        return self._display_notification(
            _('Proceso de descarga y sincronización de asistencias ejecutado.'), 'success'
        )

    def _download_pull_attendance(self, cron_mode=False):
        self.ensure_one()
        if not self.authorized:
            _logger.info("ADMS: Dispositivo %s no está autorizado. Omitiendo descarga.", self.name)
            return

        ZKLog = self.env['zk.machine.attendance'].sudo()
        RawPunch = self.env['biometric.raw.punch'].sudo()
        Employee = self.env['hr.employee'].sudo()

        tz_name = self.device_timezone or 'America/Bogota'
        try:
            device_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            device_tz = pytz.UTC

        # En cron se usa un timeout corto para no bloquear el ciclo con relojes caídos
        zk = self._get_zk_connection(timeout=8 if cron_mode else 20)
        conn = self.device_connect(zk) if zk else False
        if not conn:
            self._register_pull_result(False, _('Connection failed'))
            self.env.cr.commit()
            return

        try:
            conn.disable_device()
            attendance = conn.get_attendance() or []
            conn.enable_device()
        except Exception as e:
            self._register_pull_result(False, str(e))
            self.env.cr.commit()
            return
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

        # Descarga incremental: solo registros posteriores a la última sincronización (con margen)
        since_utc = (self.last_sync_at - timedelta(days=3)) if self.last_sync_at else None

        rows = []
        for a in attendance:
            try:
                utc_dt = device_tz.localize(a.timestamp, is_dst=None).astimezone(pytz.utc).replace(tzinfo=None)
            except Exception:
                continue
            if since_utc and utc_dt < since_utc:
                continue
            rows.append((str(a.user_id).strip(), utc_dt, a))

        if rows:
            pins = {r[0] for r in rows}
            min_dt = min(r[1] for r in rows)
            emp_by_pin = {}
            for emp in Employee.search([('device_id_num', 'in', list(pins))]):
                emp_by_pin.setdefault(emp.device_id_num, emp)

            existing_hashes = set(ZKLog.search([('punching_time', '>=', min_dt)]).mapped('hash_key'))
            existing_raw = {
                (r.biometric_id, r.punch_time)
                for r in RawPunch.with_context(active_test=False).search([
                    ('device_id', '=', self.id), ('punch_time', '>=', min_dt)
                ])
            }

            zk_vals, raw_vals = [], []
            for pin, utc_dt, a in rows:
                emp = emp_by_pin.get(pin)
                if emp and (not emp.allowed_device_ids or self.id in emp.allowed_device_ids.ids):
                    hash_key = ZKLog.compute_hash(emp.id, pin, utc_dt)
                    if hash_key not in existing_hashes:
                        existing_hashes.add(hash_key)
                        zk_vals.append({
                            'employee_id': emp.id,
                            'device_id_num': pin,
                            'punching_time': utc_dt,
                            'punch_type': str(a.punch),
                            'attendance_type': str(a.status),
                            'address_id': self.address_id.id,
                            'source_device_id': self.id,
                            'hash_key': hash_key,
                        })
                if (pin, utc_dt) not in existing_raw:
                    existing_raw.add((pin, utc_dt))
                    partner_id = False
                    if emp:
                        partner_id = emp.user_id.partner_id.id if emp.user_id else emp.work_contact_id.id
                    raw_vals.append({
                        'user_id': partner_id or False,
                        'biometric_id': pin,
                        'punch_time': utc_dt,
                        'device_id': self.id,
                        'source': 'zk',
                        'active': True,
                    })
            if zk_vals:
                ZKLog.create(zk_vals)
            if raw_vals:
                RawPunch.create(raw_vals)

        self._register_pull_result(True)
        self.write({'last_sync_at': fields.Datetime.now()})
        self.env.cr.commit()

    def action_clear_attendance_odoo(self):
        """Borra logs de marcación en Odoo únicamente para este biométrico."""
        self.ensure_one()
        if not self.env.user.has_group('hr_attendance.group_hr_attendance_manager'):
            raise UserError(_("Solo los administradores de asistencia pueden ejecutar esta acción."))
        self.env.cr.execute("DELETE FROM zk_machine_attendance WHERE source_device_id = %s", (self.id,))
        self.env.cr.execute("DELETE FROM biometric_raw_punch WHERE device_id = %s", (self.id,))
        self.env.cr.commit()
        return self._display_notification(_('Logs de marcación de este biométrico eliminados en Odoo.'), 'warning', True)

    def action_clear_attendance_device(self):
        self.ensure_one()
        if self.protocol_type == 'pull':
            zk = self._get_zk_connection(timeout=10)
            conn = self.device_connect(zk)
            if conn:
                try:
                    conn.clear_attendance()
                    conn.disconnect()
                    return self._display_notification(_('Marcaciones borradas del biométrico vía pyzk.'), 'warning', True)
                except Exception as e:
                    raise UserError(str(e))
            raise UserError(_('No se pudo conectar al dispositivo'))
        else:
            self.env['biometric.device.command'].create({
                'device_id': self.id,
                'command': 'CLEAR LOG',
                'state': 'draft'
            })
            return self._display_notification(
                _('Comando de borrado de memoria (CLEAR LOG) encolado para el biométrico.'), 'danger', True
            )

    def action_restart_device(self):
        self.ensure_one()
        if self.protocol_type == 'pull':
            zk = self._get_zk_connection(timeout=10)
            conn = self.device_connect(zk)
            if conn:
                try:
                    conn.restart()
                    conn.disconnect()
                    return self._display_notification(_('Comando de reinicio ejecutado vía pyzk.'), 'success')
                except Exception as e:
                    raise UserError(str(e))
            raise UserError(_('No se pudo conectar al dispositivo'))
        else:
            self.env['biometric.device.command'].create({
                'device_id': self.id,
                'command': 'REBOOT',
                'state': 'draft'
            })
            return self._display_notification(
                _('Comando de reinicio (REBOOT) encolado para el biométrico.'), 'success'
            )

    # ----------------------------------------------------
    # USER MAPPING WIZARDS
    # ----------------------------------------------------
    def action_open_user_mapping_wizard(self):
        self.ensure_one()
        Mapping = self.env['biometric.user.mapping']
        Employee = self.env['hr.employee']

        if self.protocol_type == 'pull':
            zk = self._get_zk_connection(timeout=30)
            conn = self.device_connect(zk)
            if not conn:
                raise UserError(_('No se pudo conectar al dispositivo biométrico por IP/Puerto.'))

            conn.disable_device()
            try:
                device_users = conn.get_users()
            except Exception as e:
                conn.disconnect()
                raise UserError(_('Error al leer usuarios del biométrico: %s') % e)

            conn.enable_device()
            conn.disconnect()

            Mapping.search([('device_id', '=', self.id)]).unlink()

            for u in device_users or []:
                pin_str = str(u.user_id).strip()
                emp = False
                candidate = Employee.search([('device_id_num', '=', pin_str)], limit=1)
                if candidate:
                    emp = candidate

                Mapping.create({
                    'device_user_id': pin_str,
                    'device_user_name': u.name or _('N/A'),
                    'employee_id': emp.id if emp else False,
                    'status': 'mapped' if emp else 'unmapped',
                    'device_id': self.id,
                })
        else:
            # ADMS:
            # 1. Encolar consulta de usuarios al reloj en segundo plano para refrescar la lista
            pending_query = self.env['biometric.device.command'].search([
                ('device_id', '=', self.id),
                ('command', '=', 'DATA QUERY tablename=user,fielddesc=*,filter=*'),
                ('state', '=', 'draft')
            ], limit=1)
            if not pending_query:
                self.env['biometric.device.command'].create({
                    'device_id': self.id,
                    'command': 'DATA QUERY tablename=user,fielddesc=*,filter=*',
                    'state': 'draft'
                })

            # 2. Sincronizar estado de los mapeos existentes ÚNICAMENTE de este dispositivo
            existing_mappings = Mapping.search([('device_id', '=', self.id)])
            for m in existing_mappings:
                vals_to_upd = {}
                target_emp = Employee.search([('device_id_num', '=', m.device_user_id)], limit=1)

                if target_emp:
                    if m.employee_id != target_emp or m.status != 'mapped':
                        vals_to_upd['employee_id'] = target_emp.id
                        vals_to_upd['status'] = 'mapped'
                else:
                    if m.employee_id or m.status != 'unmapped':
                        vals_to_upd['employee_id'] = False
                        vals_to_upd['status'] = 'unmapped'

                if vals_to_upd:
                    m.write(vals_to_upd)

        # Abrir la vista de mapeo agrupada por estado (Mapeados vs Sin Mapear)
        action = self.env['ir.actions.actions']._for_xml_id(
            'hr_zk_attendance_adms.action_biometric_user_mapping_view'
        )
        action['name'] = _('Análisis de Mapeo Biométrico: %s') % self.name
        action['domain'] = [('device_id', '=', self.id)]
        action['context'] = {
            'default_device_id': self.id,
            'search_default_group_status': 1,
            'group_by': 'status',
        }
        action['target'] = 'current'
        return action

    def action_open_odoo_to_biometric_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mapear usuarios del Odoo al biométrico'),
            'res_model': 'biometric.odoo.to.biometric.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'default_device_ids': [self.id],
            },
        }

    def action_open_multi_device_sync_wizard(self):
        device_ids = self.ids if self else self.search([('authorized', '=', True)]).ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sincronizar Usuarios en Biométricos'),
            'res_model': 'biometric.odoo.to.biometric.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_device_ids': device_ids,
            },
        }

    def action_download_device_users(self):
        """Envía orden de consulta masiva de usuarios al biométrico (SpeedFace PUSH)."""
        self.ensure_one()
        if not self.authorized:
            raise UserError(_("El dispositivo debe estar autorizado."))
        if self.protocol_type != 'adms':
            raise UserError(_("La consulta de usuarios por ADMS solo aplica a dispositivos SpeedFace / Cloud."))

        cmd_str = "DATA QUERY tablename=user,fielddesc=*,filter=*"
        self.env['biometric.device.command'].create({
            'device_id': self.id,
            'command': cmd_str,
            'state': 'draft'
        })
        return self._display_notification(
            _("Orden de consulta de usuarios enviada al biométrico. En pocos segundos el reloj sincronizará la lista completa de usuarios y nombres."),
            'success',
            False
        )

    def action_download_biophotos(self):
        """Envía orden de consulta masiva de fotos faciales al biométrico."""
        self.ensure_one()
        if not self.authorized:
            raise UserError(_("El dispositivo debe estar autorizado."))
        if self.protocol_type != 'adms':
            raise UserError(_("La descarga de fotos por ADMS solo aplica a dispositivos SpeedFace / Cloud."))

        cmd_str = "DATA QUERY tablename=biophoto,fielddesc=*,filter=*"
        self.env['biometric.device.command'].create({
            'device_id': self.id,
            'command': cmd_str,
            'state': 'draft'
        })
        return self._display_notification(
            _("Orden de consulta de fotos faciales enviada al biométrico. Las fotos se asignarán a los empleados que no tengan foto de perfil en Odoo."),
            'info',
            False
        )

    def _sync_pull_user(self, pin_str, clean_name, action):
        """Sincroniza usuario directamente al biométrico Pull vía socket pyzk (sin encolar comandos ADMS)."""
        self.ensure_one()
        if self.protocol_type != 'pull' or not self.authorized:
            return False
        zk = self._get_zk_connection(timeout=5)
        conn = self.device_connect(zk) if zk else False
        if not conn:
            _logger.warning("Biométrico Pull %s no disponible para sincronizar usuario PIN %s.", self.name, pin_str)
            return False
        try:
            users = conn.get_users() or []
            target_user = None
            existing_uids = []
            for u in users:
                existing_uids.append(u.uid)
                if str(u.user_id).strip() == pin_str:
                    target_user = u

            if action == 'enable':
                uid = target_user.uid if target_user else (max(existing_uids) + 1 if existing_uids else 1)
                conn.set_user(
                    uid=uid,
                    name=clean_name or (target_user.name if target_user else f"User {pin_str}"),
                    privilege=0,
                    password='',
                    group_id='',
                    user_id=pin_str
                )
            elif action == 'delete' and target_user:
                conn.delete_user(uid=target_user.uid)
            elif action == 'disable':
                _logger.info("Pull device %s: solicitud de inhabilitar PIN %s registrada.", self.name, pin_str)
            return True
        except Exception as e:
            _logger.error("Error en pyzk sincronizando usuario PIN %s en %s: %s", pin_str, self.name, e)
            return False
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

    def _enqueue_user_command(self, pin, name=None, action='enable'):
        """
        Encola o despacha un comando de usuario para este dispositivo.
        action:
          - 'enable': Carga/Actualiza el usuario con acceso permitido
          - 'disable': Desactiva el usuario con Disable=1 (acceso restringido, preserva plantillas biométricas)
          - 'delete': Elimina el usuario del reloj (DATA DELETE user Pin=...)
        """
        self.ensure_one()
        if not pin or not self.authorized:
            return

        pin_str = str(pin).strip()
        clean_name = (name or '').strip().replace('\t', ' ').replace('\n', ' ')

        # Para dispositivos de red local (Pull), no usar cola ADMS
        if self.protocol_type == 'pull':
            return self._sync_pull_user(pin_str, clean_name, action)

        if action == 'enable':
            cmd_str = f"DATA UPDATE user Pin={pin_str}\tCardNo=\tPassword=\tGroup=1\tStartTime=0\tEndTime=0\tName={clean_name}\tPrivilege=0" if clean_name else f"DATA UPDATE user Pin={pin_str}\tDisable=0"
        elif action == 'disable':
            cmd_str = f"DATA UPDATE user Pin={pin_str}\tDisable=1"
        elif action == 'delete':
            cmd_str = f"DATA DELETE user Pin={pin_str}"
        else:
            return

        Command = self.env['biometric.device.command']
        # Buscar comandos pendientes draft que contengan el mismo Pin en este dispositivo
        pending = Command.search([
            ('device_id', '=', self.id),
            ('state', '=', 'draft')
        ])
        for c in pending:
            parts = (c.command or '').replace('\t', ' ').split()
            c_pin = False
            for part in parts:
                if part.lower().startswith('pin='):
                    c_pin = part.split('=', 1)[1].strip()
                    break
            if c_pin == pin_str:
                if c.command == cmd_str:
                    # Ya está el mismo comando exacto pendiente, no duplicar
                    return
                # Si es un comando previo conflictivo (ej. borrador previo), descartar el viejo
                c.unlink()

        Command.create({
            'device_id': self.id,
            'command': cmd_str,
            'state': 'draft'
        })

    def _enqueue_user_photo(self, pin, image_data):
        """
        Encola el comando DATA UPDATE biophoto para SpeedFace / ADMS tras optimizar la foto.
        """
        self.ensure_one()
        if not pin or not self.authorized or self.protocol_type != 'adms':
            return False

        res = optimize_biophoto(image_data)
        if not res:
            return False

        bin_size, clean_b64 = res
        pin_str = str(pin).strip()
        cmd_str = f"DATA UPDATE biophoto Pin={pin_str}\tPIN={pin_str}\tFileName={pin_str}.jpg\tType=9\tSize={bin_size}\tContent={clean_b64}"

        Command = self.env['biometric.device.command']
        pending = Command.search([
            ('device_id', '=', self.id),
            ('state', '=', 'draft')
        ])
        for c in pending:
            if 'biophoto' in (c.command or '') and f"Pin={pin_str}" in c.command:
                c.unlink()

        Command.create({
            'device_id': self.id,
            'command': cmd_str,
            'state': 'draft'
        })
        _logger.info("ADMS: Comando biophoto encolado para PIN %s en %s (Tamaño: %d bytes)", pin_str, self.name, bin_size)
        return True


    # ----------------------------------------------------
    # CRON ENTRY POINT
    # ----------------------------------------------------
    PULL_BACKOFF_MINUTES = [5, 15, 30, 60]   # escalado tras fallos consecutivos
    CMD_SENT_TIMEOUT_MIN = 15                # 'sent' sin confirmación -> error
    CMD_HISTORY_DAYS = 30                    # purga de comandos finalizados (30 días)

    @api.model
    def cron_download(self):
        now = fields.Datetime.now()
        pull_devices = self.search([
            ('protocol_type', '=', 'pull'),
            ('authorized', '=', True),
            '|', ('pull_next_retry', '=', False), ('pull_next_retry', '<=', now),
        ])
        for dev in pull_devices:
            try:
                dev._download_pull_attendance(cron_mode=True)
            except Exception as e:
                _logger.error("Error descargando marcaciones Pull de %s: %s", dev.name, e)
        self._sync_to_hr_attendance()
        self._cron_command_housekeeping()

    @api.model
    def _cron_command_housekeeping(self):
        """Marca como error los comandos ADMS 'sent' sin confirmación y purga historial antiguo."""
        Command = self.env['biometric.device.command'].sudo()
        now = fields.Datetime.now()
        stale = Command.search([
            ('state', '=', 'sent'),
            ('sent_at', '<', now - timedelta(minutes=self.CMD_SENT_TIMEOUT_MIN)),
        ])
        if stale:
            stale.write({'state': 'error', 'return_code': 'TIMEOUT'})
        old = Command.search([
            ('state', 'in', ('done', 'error')),
            ('create_date', '<', now - timedelta(days=self.CMD_HISTORY_DAYS)),
        ])
        if old:
            old.unlink()

    def _register_pull_result(self, success, error_msg=None):
        """Actualiza estado y backoff de un dispositivo Pull."""
        self.ensure_one()
        if success:
            self.write({
                'status': 'ok', 'last_error': False,
                'pull_fail_count': 0, 'pull_next_retry': False,
            })
        else:
            fails = (self.pull_fail_count or 0) + 1
            idx = min(fails - 1, len(self.PULL_BACKOFF_MINUTES) - 1)
            self.write({
                'status': 'error',
                'last_error': error_msg or _('Connection failed'),
                'pull_fail_count': fails,
                'pull_next_retry': fields.Datetime.now() + timedelta(minutes=self.PULL_BACKOFF_MINUTES[idx]),
            })

    @api.model
    def cron_connection_test(self):
        pull_devices = self.search([('protocol_type', '=', 'pull'), ('authorized', '=', True)])
        for dev in pull_devices:
            dev._test_connection_logic()

    # ----------------------------------------------------
    # SYNC TO HR.ATTENDANCE (UPSERT & SESSION MATCHING)
    # ----------------------------------------------------
    def _sync_to_hr_attendance(self, employee_ids=None):
        """
        Sincroniza la Vista 'daily.attendance' con la tabla nativa 'hr.attendance'.
        Estrategia: Upsert basado en coincidencia de Sesión/Empleado.
        Optimización: Pre-fetching en memoria para evitar consultas N+1.

        :param employee_ids: lista opcional de IDs de empleado; si se indica, solo
                             se sincronizan esos empleados (usado en el push ADMS).

        Nota: anteriormente cualquier dispositivo en estado 'error' anulaba TODAS las
        salidas (check_out) de todos los empleados. Se eliminó: si llega una marcación
        tardía, la salida se corrige en el siguiente ciclo (el upsert actualiza check_out).
        """
        _logger.debug("Starting ADMS Sync to HR Attendance...")

        limit_date = fields.Date.today() - timedelta(days=30)
        domain = [('punching_day', '>=', limit_date)]
        if employee_ids:
            domain.append(('employee_id', 'in', list(employee_ids)))
        daily_logs = self.env['daily.attendance'].sudo().search(domain, order='punching_day asc')

        if not daily_logs:
            return

        HrAttendance = self.env['hr.attendance'].sudo()
        
        min_date = daily_logs[0].punching_day - timedelta(days=2)
        involved_employees = daily_logs.mapped('employee_id')
        
        all_candidates = HrAttendance.search([
            ('employee_id', 'in', involved_employees.ids),
            ('check_in', '>=', min_date),
        ])
        
        candidates_by_emp = {}
        for att in all_candidates:
            emp_id = att.employee_id.id
            if emp_id not in candidates_by_emp:
                candidates_by_emp[emp_id] = []
            candidates_by_emp[emp_id].append(att)
            
        open_attendances = HrAttendance.search([
            ('employee_id', 'in', involved_employees.ids),
            ('check_out', '=', False)
        ])
        open_by_emp = {}
        for att in open_attendances:
            if att.employee_id.id not in open_by_emp:
                open_by_emp[att.employee_id.id] = []
            open_by_emp[att.employee_id.id].append(att)

        # Si algún dispositivo AUTORIZADO está caído, se activa peligro para
        # no cerrar asistencias hasta que dicho reloj se restablezca o se desautorice.
        any_auth_device_error = self.search_count([
            ('status', '=', 'error'),
            ('authorized', '=', True)
        ])
        is_global_danger = any_auth_device_error > 0

        for log in daily_logs:
            if not log.employee_id:
                continue

            emp_id = log.employee_id.id
            check_in = log.check_in
            check_out = log.check_out
            
            if log.is_danger or is_global_danger:
                check_out = False
            
            company_tz_name = 'America/Bogota'
            if log.employee_id.company_id.partner_id.tz:
                company_tz_name = log.employee_id.company_id.partner_id.tz
            
            emp_tz = pytz.timezone(company_tz_name)
            emp_candidates = candidates_by_emp.get(emp_id, [])
            
            target_attendance = False
            
            # Margen +/- 18h
            limit_start = check_in - timedelta(hours=18)
            limit_end = check_in + timedelta(hours=18)
            
            matches = [att for att in emp_candidates if limit_start <= att.check_in <= limit_end]
            
            for att in matches:
                att_local = pytz.utc.localize(att.check_in).astimezone(emp_tz)
                if att_local.date() == log.punching_day or att.check_in == log.check_in:
                    target_attendance = att
                    break
            
            if not target_attendance:
                limit_prox_start = check_in - timedelta(hours=12)
                limit_prox_end = check_in + timedelta(hours=12)
                sorted_candidates = sorted(emp_candidates, key=lambda x: x.check_in, reverse=True)
                for att in sorted_candidates:
                    if limit_prox_start <= att.check_in <= limit_prox_end:
                        closest_local = pytz.utc.localize(att.check_in).astimezone(emp_tz)
                        if closest_local.date() == log.punching_day:
                            target_attendance = att
                            break

            if not target_attendance:
                emp_opens = open_by_emp.get(emp_id, [])
                last_open_att = False
                if emp_opens:
                    emp_opens.sort(key=lambda x: x.check_in, reverse=True)
                    last_open_att = emp_opens[0]
                
                if last_open_att:
                    time_diff = check_in - last_open_att.check_in
                    if abs(time_diff.total_seconds()) < 24 * 3600:
                        target_attendance = last_open_att
                    else:
                        for open_att in emp_opens:
                            if open_att.check_in < check_in:
                                try:
                                    with self.env.cr.savepoint():
                                        _logger.warning("Auto-closing stuck attendance for %s", log.employee_id.name)
                                        force_out = open_att.check_in + timedelta(minutes=1)
                                        open_att.write({'check_out': force_out})
                                except Exception:
                                    pass

            if target_attendance:
                vals = {}
                if check_in < target_attendance.check_in:
                    vals['check_in'] = check_in
                
                current_out = target_attendance.check_out
                if (not check_out) and current_out:
                    pass
                elif check_out and check_out != current_out:
                    vals['check_out'] = check_out
                
                if vals:
                    try:
                        with self.env.cr.savepoint():
                            target_attendance.write(vals)
                    except Exception:
                        pass
            else:
                open_blocker = HrAttendance.search([
                    ('employee_id', '=', log.employee_id.id),
                    ('check_out', '=', False)
                ], order='check_in desc', limit=1)

                if open_blocker:
                    if open_blocker.check_in < check_in:
                        # Asistencia abierta anterior a esta sesión: cerrarla al inicio de la nueva
                        try:
                            with self.env.cr.savepoint():
                                open_blocker.write({'check_out': check_in})
                        except Exception:
                            pass
                    elif not check_out:
                        # La asistencia abierta es POSTERIOR a esta sesión sin salida:
                        # Odoo no permite crear otra abierta. Se omite (sin reintentos ruidosos).
                        _logger.debug(
                            "Sesión %s de %s omitida: existe asistencia abierta posterior (%s).",
                            log.punching_day, log.employee_id.name, open_blocker.check_in
                        )
                        continue

                vals = {
                    'employee_id': log.employee_id.id,
                    'check_in': check_in,
                }
                if check_out:
                    vals['check_out'] = check_out

                try:
                    with self.env.cr.savepoint():
                        new_att = HrAttendance.create(vals)
                        if emp_id not in candidates_by_emp:
                            candidates_by_emp[emp_id] = []
                        candidates_by_emp[emp_id].append(new_att)
                except ValidationError as e:
                    _logger.debug("hr.attendance no creada para %s (%s): %s", log.employee_id.name, log.punching_day, e)
                except Exception as e:
                    _logger.error("Error creating hr.attendance for %s: %s", log.employee_id.name, e)
