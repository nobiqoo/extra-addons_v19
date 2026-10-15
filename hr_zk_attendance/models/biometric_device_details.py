# -*- coding: utf-8 -*-
import logging
import pytz
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

try:
    from zk import ZK
except ImportError:
    _logger.error("Please install pyzk (pip install pyzk). Module import name is 'zk'.")


class BiometricDeviceDetails(models.Model):
    _name = 'biometric.device.details'
    _description = 'Biometric Device Details'

    # ----------------------------------------------------
    # FIELDS
    # ----------------------------------------------------
    name = fields.Char(required=True, help='Record Name')
    device_ip = fields.Char(string='Device IP', required=True)
    port_number = fields.Integer(string='Port Number', required=True, default=4370)
    address_id = fields.Many2one('res.partner', string='Working Address')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True
    )
    
    device_timezone = fields.Selection(
        '_get_timezones',
        string='Device Timezone',
        default='UTC',
        required=True,
        help="Timezone of the device location. Used to correctly convert device logs to UTC."
    )

    last_sync_at = fields.Datetime(readonly=True)
    status = fields.Selection(
        [('idle', 'Idle'), ('ok', 'OK'), ('error', 'Error'), ('syncing', 'Syncing')],
        default='idle',
        readonly=True,
    )
    last_error = fields.Text(readonly=True)

    @api.model
    def _get_timezones(self):
        return [(tz, tz) for tz in pytz.all_timezones]

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
            _logger.error("Please install pyzk (pip install pyzk). Module import name is 'zk'.")
            return None

        return ZK(
            self.device_ip,
            port=self.port_number,
            timeout=timeout,
            password=0,
            force_udp=False,
            # Odoo.sh may block ICMP ping even when the ZK TCP port is reachable.
            ommit_ping=True,
        )



    def device_connect(self, zk_obj):
        try:
            return zk_obj.connect()
        except Exception:
            return False

    # ----------------------------------------------------
    # DEVICE ACTIONS
    # ----------------------------------------------------
    def action_test_connection(self):
        self.ensure_one()
        # Reusing the private method for consistency, but raising error for UI feedback
        success, error_msg = self._test_connection_logic()
        if success:
             return self._display_notification(_('Successfully Connected'), 'success')
        else:
             raise ValidationError(error_msg)

    def _test_connection_logic(self):
        """
        Internal helper to test connection.
        Returns: (bool, str|None) -> (Success, Error Message)
        Side Effects: Updates status, last_error, last_sync_at
        """
        self.ensure_one()
        try:
            zk = self._get_zk_connection(timeout=10)
            conn = zk.connect()
            if conn:
                conn.disconnect()
                self.write({
                    'status': 'ok',
                    'last_error': False,
                    # We might update last_sync_at only on full sync, but valid connection is also good info.
                    # Let's keep last_sync_at for DATA sync, and maybe just update status here.
                })
                return True, None
        except Exception as e:
            self.write({'status': 'error', 'last_error': str(e)})
            return False, str(e)
        
        # Fallback if connect() returns false without exception
        self.write({'status': 'error', 'last_error': 'Unknown Connection Failure'})
        return False, 'Unknown Connection Failure'

    @api.model
    def cron_connection_test(self):
        """
        Cron job to test connection of all devices.
        Uses SKIP LOCKED to avoid colliding with long-running download jobs.
        """
        # Get IDs first
        ids = self.search([]).ids
        for dev_id in ids:
            # 1. ATTEMPT DB LOCK (Non-blocking)
            # If the row is locked (e.g. by Download Data cron), this returns None immediately.
            self.env.cr.execute("SELECT id FROM biometric_device_details WHERE id = %s FOR UPDATE SKIP LOCKED", (dev_id,))
            if not self.env.cr.fetchone():
                _logger.debug(f"Skipping Health Check for Device ID {dev_id}: Row is locked by another process.")
                continue

            # 2. Proceed with business logic
            try:
                with self.env.cr.savepoint():
                    dev = self.browse(dev_id)
                    
                    # Double check status (logic layer check)
                    if dev.status == 'syncing':
                         _logger.debug(f"Skipping health check for {dev.name} because it is syncing.")
                         continue

                    dev._test_connection_logic()
                    
                    # FORCE WRITE: Flush immediately to execute UPDATE while we hold the lock
                    dev.flush_recordset()
            except Exception as e:
                _logger.error(f"Error checking device {dev_id}: {str(e)}")
                
    def action_set_timezone(self):
        self.ensure_one()
        zk = self._get_zk_connection(timeout=15)
        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_("Please Check the Connection"))

        # Use device timezone for setting time too!
        tz_name = self.device_timezone or 'UTC'
        try:
            dev_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            dev_tz = pytz.UTC
            
        now_utc = fields.Datetime.now()
        local_dt = pytz.utc.localize(now_utc).astimezone(dev_tz)
        conn.set_time(local_dt)
        conn.disconnect()
        return self._display_notification(_('Time synchronized'), 'success')

    # ----------------------------------------------------
    # USER MAPPING
    # ----------------------------------------------------
    def action_open_user_mapping_wizard(self):
        self.ensure_one()

        zk = self._get_zk_connection(timeout=30)
        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Unable to connect to device.'))

        conn.disable_device()
        try:
            device_users = conn.get_users()
        except Exception as e:
            raise UserError(_('Error reading users: %s') % e)
        finally:
            try:
                conn.enable_device()
            finally:
                conn.disconnect()

        self.env['biometric.user.mapping'].search(
            [('device_id', '=', self.id)]
        ).unlink()

        for u in device_users or []:
            emp = self.env['hr.employee'].search(
                [('device_id_num', '=', u.user_id)], limit=1
            )
            self.env['biometric.user.mapping'].create({
                'device_user_id': u.user_id,
                'device_user_name': u.name or _('N/A'),
                'employee_id': emp.id if emp else False,
                'status': 'mapped' if emp else 'unmapped',
                'device_id': self.id,
            })

        action = self.env['ir.actions.actions']._for_xml_id(
            'hr_zk_attendance.action_biometric_user_mapping_view'
        )
        action['domain'] = [('device_id', '=', self.id)]
        return action

    def action_open_odoo_to_biometric_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mapear usuarios del Odoo al biométrico'),
            'res_model': 'biometric.odoo.to.biometric.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    # ----------------------------------------------------
    # CRON ENTRY POINT
    # ----------------------------------------------------
    @api.model
    def cron_download(self):
        self.search([]).action_download_attendance()

    @api.model
    def cron_sync_time(self):
        """
        Cron job to periodically sync the Odoo server time (adjusted by device timezone)
        to all biometric devices.
        """
        for dev in self.search([]):
            try:
                zk = dev._get_zk_connection(timeout=15)
                conn = dev.device_connect(zk)
                if not conn:
                    _logger.warning(f"Time sync failed for {dev.name}: Cannot connect.")
                    continue
                
                tz_name = dev.device_timezone or 'UTC'
                try:
                    dev_tz = pytz.timezone(tz_name)
                except pytz.UnknownTimeZoneError:
                    dev_tz = pytz.UTC
                    
                now_utc = fields.Datetime.now()
                local_dt = pytz.utc.localize(now_utc).astimezone(dev_tz)
                
                conn.set_time(local_dt)
                conn.disconnect()
                _logger.info(f"Time synchronized successfully for {dev.name} to {local_dt}")
            except Exception as e:
                _logger.error(f"Error syncing time for {dev.name}: {str(e)}")

    # ----------------------------------------------------
    # ATTENDANCE DOWNLOAD (SAFE / MULTI-BIOMETRIC)
    # ----------------------------------------------------
    def action_download_attendance(self):
        ZKLog = self.env['zk.machine.attendance'].sudo()
        # REMOVED user_tz global var, moving to per-device loop

        for dev in self:
            # FIX CONCURRENCY: Lock the row explicitly to wait for any running Health Check to finish.
            # This prevents "SerializationFailure: could not serialize access due to concurrent update"
            self.env.cr.execute("SELECT id FROM biometric_device_details WHERE id = %s FOR UPDATE", (dev.id,))
            
            dev.write({'status': 'syncing', 'last_error': False})
            # FIX CONCURRENCY: Commit status immediately so other crons see it
            self.env.cr.commit()

            
            # Resolve Device Timezone
            tz_name = dev.device_timezone or 'UTC'
            try:
                device_tz = pytz.timezone(tz_name)
            except pytz.UnknownTimeZoneError:
                device_tz = pytz.UTC

            zk = dev._get_zk_connection(timeout=20)

            conn = self.device_connect(zk)
            if not conn:
                dev.write({'status': 'error', 'last_error': _('Connection failed')})
                continue

            try:
                conn.disable_device()
                attendance = conn.get_attendance() or []
            except Exception as e:
                dev.write({'status': 'error', 'last_error': str(e)})
                continue
            finally:
                try:
                    conn.enable_device()
                finally:
                    conn.disconnect()

            for a in attendance:
                # Use DEVICE timezone, not user timezone
                local_dt = device_tz.localize(a.timestamp, is_dst=None)
                utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                
                #_logger.info(f"DEBUG TIMEZONE: Device={dev.name} | Raw={a.timestamp} | TZ={device_tz} | Local={local_dt} | UTC={utc_dt}")

                # Búsqueda tolerante a ceros iniciales
                search_domains = [('device_id_num', '=', a.user_id)]
                if isinstance(a.user_id, str):
                    stripped_id = a.user_id.lstrip('0') or '0'
                    if stripped_id != a.user_id:
                        search_domains = ['|', ('device_id_num', '=', a.user_id), ('device_id_num', '=', stripped_id)]

                emp = self.env['hr.employee'].sudo().search(
                    search_domains,
                    limit=1
                )
                if not emp:
                    continue

                # --- Whitelist Check ---
                # Si el empleado tiene dispositivos permitidos, verificar que este sea uno de ellos.
                is_allowed = True
                if emp.allowed_device_ids and dev.id not in emp.allowed_device_ids.ids:
                    is_allowed = False

                if is_allowed:
                    hash_key = ZKLog.compute_hash(
                        emp.id,
                        a.user_id,
                        utc_dt
                    )

                    if not ZKLog.search_count([('hash_key', '=', hash_key)]):
                        ZKLog.create({
                            'employee_id': emp.id,
                            'device_id_num': a.user_id,
                            'punching_time': utc_dt,
                            'punch_type': str(a.punch),
                            'attendance_type': str(a.status),
                            'address_id': dev.address_id.id,
                            'source_device_id': dev.id,
                            'hash_key': hash_key,
                        })

                # --- NEW LOGIC: Populate biometric.raw.punch ---
                # Verificar duplicados en raw punch
                existing_raw = self.env['biometric.raw.punch'].sudo().search_count([
                    ('biometric_id', '=', a.user_id),
                    ('punch_time', '=', utc_dt),
                    ('device_id', '=', dev.id),
                ])
                
                if not existing_raw:
                    # Intentar obtener el partner del empleado
                    # Si el empleado no tiene partner (address_home_id o user_id.partner_id), 
                    # usamos address_id del dispositivo como fallback o fallamos controlado?
                    # El campo user_id en raw.punch es obligatorio.
                    
                    partner_id = False
                    if emp.user_id:
                        partner_id = emp.user_id.partner_id.id
                    elif hasattr(emp, 'work_contact_id') and emp.work_contact_id:
                         partner_id = emp.work_contact_id.id
                    elif hasattr(emp, 'address_home_id') and emp.address_home_id:
                         partner_id = emp.address_home_id.id
                    
                    self.env['biometric.raw.punch'].sudo().create({
                        'employee_id': emp.id,
                        'user_id': partner_id or False,
                        'biometric_id': a.user_id,
                        'punch_time': utc_dt,
                        'device_id': dev.id,
                        'source': 'zk',
                        'active': True,
                    })

            dev.write({
                'status': 'ok',
                'last_sync_at': fields.Datetime.now(),
                'last_error': False,
            })
            # FIX CONCURRENCY: Commit transaction after finishing THIS device to release locks
            # and allow other processes to touch it if needed, and to ensure NEXT device
            # starts with a fresh transaction snapshot.
            self.env.cr.commit()
        
        # --- TRIGGER SYNC TO HR.ATTENDANCE ---
        self._sync_to_hr_attendance()

    def _sync_to_hr_attendance(self):
        """
        Sincroniza la Vista 'daily.attendance' con la tabla nativa 'hr.attendance'.
        Estrategia: Upsert (Crear o Actualizar) basado en coincidencia de Día/Empleado.
        OPTIMIZACION: Pre-fetching de datos para evitar consultas N+1.
        """
        _logger.debug("Starting Sync to HR Attendance...")
        
        # 1. GLOBAL SAFETY CHECK
        any_device_error = self.env['biometric.device.details'].search_count([
            ('status', '=', 'error')
        ])
        is_global_danger = any_device_error > 0
        
        if is_global_danger:
            _logger.warning("Global Safety Check Failed: At least one device is in error state. Sync will be CAUTIOUS (No Closings).")

        # 2. FETCH DATA
        limit_date = fields.Date.today() - timedelta(days=30)
        daily_logs = self.env['daily.attendance'].sudo().search([
            ('punching_day', '>=', limit_date)
        ], order='punching_day asc')

        if not daily_logs:
            return

        HrAttendance = self.env['hr.attendance'].sudo()
        
        # --- OPTIMIZATION START: Pre-fetch existing attendance ---
        min_date = daily_logs[0].punching_day - timedelta(days=2) # Margin for TZ and search
        max_date = daily_logs[-1].punching_day + timedelta(days=2)
        involved_employees = daily_logs.mapped('employee_id')
        
        # Fetch ALL candidates in one go
        all_candidates = HrAttendance.search([
            ('employee_id', 'in', involved_employees.ids),
            ('check_in', '>=', min_date), # Approximate range, refined in memory
             # We don't cap by max_check_in heavily ensuring we get open ones too if needed
        ])
        
        # Organize in a dict for fast access: { employee_id: [att_records sorted] }
        candidates_by_emp = {}
        for att in all_candidates:
            emp_id = att.employee_id.id
            if emp_id not in candidates_by_emp:
                candidates_by_emp[emp_id] = []
            candidates_by_emp[emp_id].append(att)
            
        # Also need "Open" attendances specifically? 
        # The 'all_candidates' might miss very old open attendances that are blocking actions today?
        # Let's search for ANY open attendance for these employees to be safe/correct (blocking check)
        open_attendances = HrAttendance.search([
            ('employee_id', 'in', involved_employees.ids),
            ('check_out', '=', False)
        ])
        open_by_emp = {}
        for att in open_attendances:
            if att.employee_id.id not in open_by_emp:
                open_by_emp[att.employee_id.id] = []
            open_by_emp[att.employee_id.id].append(att)
            
        # --- END OPTIMIZATION PRE-FETCH ---

        for log in daily_logs:
            if not log.employee_id:
                continue

            emp_id = log.employee_id.id
            check_in = log.check_in
            check_out = log.check_out
            
            if log.is_danger or is_global_danger:
                check_out = False
            
            # --- LOCALIZATION ---
            company_tz_name = 'America/Bogota'
            if log.employee_id.company_id.partner_id.tz:
                company_tz_name = log.employee_id.company_id.partner_id.tz
            
            emp_tz = pytz.timezone(company_tz_name)
            
            # Use In-Memory Candidates
            emp_candidates = candidates_by_emp.get(emp_id, [])
            
            target_attendance = False
            
            # Filter candidates for the +/- 18h range
            matches = []
            limit_start = check_in - timedelta(hours=18)
            limit_end = check_in + timedelta(hours=18)
            
            for att in emp_candidates:
                if att.check_in >= limit_start and att.check_in <= limit_end:
                    matches.append(att)
            
            for att in matches:
                att_local = pytz.utc.localize(att.check_in).astimezone(emp_tz)
                if att_local.date() == log.punching_day:
                    target_attendance = att
                    break
                if att.check_in == log.check_in:
                    target_attendance = att
                    break
            
            # --- FALLBACK 2: PROXIMITY ---
            if not target_attendance:
                 # In-Memory Proximity search
                 limit_prox_start = check_in - timedelta(hours=12)
                 limit_prox_end = check_in + timedelta(hours=12)
                 
                 # Manual sort desc
                 sorted_candidates = sorted(emp_candidates, key=lambda x: x.check_in, reverse=True)
                 
                 closest_att = False
                 for att in sorted_candidates:
                     if att.check_in >= limit_prox_start and att.check_in <= limit_prox_end:
                         closest_att = att
                         break # Found the first one (desc update)
                 
                 if closest_att:
                      closest_local = pytz.utc.localize(closest_att.check_in).astimezone(emp_tz)
                      if closest_local.date() == log.punching_day:
                          target_attendance = closest_att

            # --- FALLBACK 3: BLOCKING OPEN ATTENDANCE ---
            if not target_attendance:
                # Use open_by_emp cache
                emp_opens = open_by_emp.get(emp_id, [])
                # Get the 'last' open (most recent check in)
                last_open_att = False
                if emp_opens:
                    # Sort desc by check_in
                    emp_opens.sort(key=lambda x: x.check_in, reverse=True)
                    last_open_att = emp_opens[0]
                
                if last_open_att:
                    time_diff = check_in - last_open_att.check_in
                    if abs(time_diff.total_seconds()) < 24 * 3600:
                         target_attendance = last_open_att
                    else:
                         # Stuck attendance logic
                         # Close all open attendances older than check_in
                         for open_att in emp_opens:
                             if open_att.check_in < check_in:
                                 try:
                                     with self.env.cr.savepoint():
                                         _logger.warning(f"Auto-closing stuck attendance for {log.employee_id.name} from {open_att.check_in}")
                                         force_out = open_att.check_in + timedelta(minutes=1)
                                         open_att.write({'check_out': force_out}) 
                                 except Exception:
                                     pass

            # 4. UPSERT ACTION
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
                # Create NEW
                # Safety check (already cached in open_by_emp, need to re-verify if we modified it? 
                # Actually, if we closed stuck attendances above, we are safe.
                # But one edge case: Is there an open blocker that we didn't catch in Fallback 3?
                # The 'last_open_att' logic above covers the blocking scenario.
                # But let's be safe and check the cache again.
                
                # NOTE: Since we are modifying DB in the loop, the cache 'open_by_emp' becomes stale!
                # However, for a *single* run, we assume consistent state or we accept minor race.
                # To be safer, we could just run the quick existing query here (`limit=1`) as it's rare (only on creation).
                # Reducing N+1 on Creation is less critical than on Sync/Update.
                # Let's keep the safety query:
                
                open_blocker = HrAttendance.search([
                    ('employee_id', '=', log.employee_id.id),
                    ('check_out', '=', False)
                ], limit=1)
                
                if open_blocker:
                    try:
                        with self.env.cr.savepoint():
                            _logger.warning(f"Final Safety: Closing blocking attendance {open_blocker.check_in} for {log.employee_id.name} to allow creation.")
                            open_blocker.write({'check_out': open_blocker.check_in + timedelta(minutes=1)})
                            open_blocker.flush_recordset()
                    except Exception:
                        pass

                # Re-validar duplicados con busqueda FUZZY (Rango de 2 segundos)
                # Keep this query for safety too
                exists_fuzzy = HrAttendance.search_count([
                    ('employee_id', '=', log.employee_id.id),
                    ('check_in', '>=', check_in - timedelta(seconds=2)),
                    ('check_in', '<=', check_in + timedelta(seconds=2))
                ])
                
                if not exists_fuzzy:
                    try:
                        with self.env.cr.savepoint():
                            HrAttendance.create({
                                'employee_id': log.employee_id.id,
                                'check_in': check_in,
                                'check_out': check_out
                            })
                            # Add to cache for subsequent loops?
                            # Not strictly necessary if logs are ordered by day, but good practice if complexity allows.
                    except Exception as e:
                        _logger.debug(f"Skipping duplicate/conflict for {log.employee_id.name}: {str(e)}")
                        pass

    # ----------------------------------------------------
    # MAINTENANCE ACTIONS
    # ----------------------------------------------------
    def action_clear_attendance_odoo(self):
        self.env.cr.execute("DELETE FROM zk_machine_attendance")
        self.env.cr.execute("DELETE FROM biometric_raw_punch")
        self.env.cr.execute("DELETE FROM hr_attendance")
        self.env.cr.commit()
        return self._display_notification(_('ODOO logs cleared'), 'warning', True)

    def action_clear_attendance_device(self):
        self.ensure_one()
        zk = self._get_zk_connection(timeout=15)
        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Cannot connect to device'))
        conn.clear_attendance()
        conn.disconnect()
        return self._display_notification(_('Device logs cleared'), 'danger', True)

    def action_restart_device(self):
        self.ensure_one()
        zk = self._get_zk_connection(timeout=15)
        conn = self.device_connect(zk)
        if not conn:
            raise UserError(_('Cannot connect to device'))
        try:
            conn.restart()
        finally:
            conn.disconnect()
        return self._display_notification(_('Device restart command sent'), 'success')
