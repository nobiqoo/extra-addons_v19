# -*- coding: utf-8 -*-
import logging
import pytz
import hashlib
from datetime import datetime

from odoo import http, fields, api, SUPERUSER_ID, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class ZkAdmsController(http.Controller):

    @http.route('/iclock/ping', type='http', auth='none', methods=['GET'], csrf=False)
    def iclock_ping(self, **kw):
        return "PONG"

    def _get_client_ip(self):
        headers = request.httprequest.headers
        forwarded = headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return headers.get('X-Real-IP') or request.httprequest.remote_addr

    def _get_env(self, kw):
        """Obtiene un environment seguro para peticiones auth='none'."""
        db_name = kw.get('db') or request.params.get('db')
        if not db_name:
            if hasattr(request, 'session') and request.session.db:
                db_name = request.session.db
            else:
                dbs = http.db_list(force=True)
                if len(dbs) == 1:
                    db_name = dbs[0]

        if not db_name:
            _logger.error("ADMS: No se pudo determinar la base de datos de Odoo. Agregue ?db=NOMBRE_BD al URL del servidor.")
            return None, None

        import odoo
        registry = odoo.modules.registry.Registry(db_name)
        cr = registry.cursor()
        env = api.Environment(cr, SUPERUSER_ID, {})
        return env, cr

    @http.route('/iclock/cdata', type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def iclock_cdata(self, **kw):
        """
        Endpoint principal para:
        1. Handshake de opciones (GET con options=all)
        2. Recepción de marcaciones en tiempo real (POST con table=ATTLOG o table=rtlog)
        """
        sn = kw.get('SN')
        if not sn:
            return "ERROR: Missing SN"

        env, cr = self._get_env(kw)
        if not env:
            return "ERROR: Missing DB"

        try:
            client_ip = self._get_client_ip()
            Device = env['biometric.device.details'].sudo()
            device = Device.search([('sn', '=', sn)], limit=1)

            # Auto-registrar el dispositivo si es la primera vez que se comunica
            if not device:
                device = Device.create({
                    'name': f'SpeedFace ({sn})',
                    'sn': sn,
                    'device_ip': client_ip,
                    'status': 'ok',
                    'authorized': False,
                    'protocol_type': 'adms',
                    'last_heartbeat': fields.Datetime.now()
                })
                _logger.info(f"ADMS: Nuevo biométrico detectado y registrado automáticamente (No autorizado por defecto): {sn}")
            else:
                device.write({
                    'device_ip': client_ip,
                    'last_heartbeat': fields.Datetime.now(),
                    'status': 'ok',
                    'last_error': False
                })

            table = kw.get('table', '')

            # --- CASO 1: Handshake de Opciones (GET /iclock/cdata?options=all) ---
            if request.httprequest.method == 'GET' and ('options' in kw or not table):
                reg_code = hashlib.md5(f"zk_{sn}".encode()).hexdigest()[:16]
                v3 = (sn and sn.upper().startswith(("WCF", "H", "SF", "PF", "VF", "UFACE")))
                trans_flag = "TransData AttLog\tOpLog\tAttPhoto\tEnrollUser\tChgUser\tEnrollFP\tChgFP\tFACE\tUserPic\tBioPhoto\tBioData" if v3 else "111111111111"
                response_txt = (
                    f"GET OPTION FROM: {sn}\n"
                    f"RegistryCode={reg_code}\n"
                    "ATTLOGStamp=0\n"
                    "OPERLOGStamp=0\n"
                    "ATTPHOTOStamp=0\n"
                    "Stamp=0\n"
                    "OpStamp=0\n"
                    "PhotoStamp=9999\n"
                    "ErrorDelay=30\n"
                    "Delay=30\n"
                    "TransTimes=00:00;14:00\n"
                    "TransInterval=1\n"
                    f"TransFlag={trans_flag}\n"
                    "Realtime=1\n"
                    "Encrypt=0\n"
                    "PushOptionsFlag=1\n"
                    "PushProtVer=3.1.2\n"
                    "ServerVersion=3.1.1\n"
                    "ServerVer=3.1.1\n"
                )
                cr.commit()
                return request.make_response(response_txt, headers=[('Content-Type', 'text/plain')])

            # --- CASO 2: Recepción de marcaciones de asistencia (table=ATTLOG o table=rtlog) ---
            if table in ('ATTLOG', 'rtlog'):
                if not device.authorized:
                    _logger.warning(f"ADMS: Marcaciones descartadas porque el biométrico NO está autorizado: {sn} ({device.name})")
                    cr.commit()
                    return "OK"

                raw_data = request.httprequest.get_data().decode('utf-8', errors='ignore')
                _logger.info(f"ADMS {table} recibido de {sn}:\n{raw_data}")

                lines = [line.strip() for line in raw_data.strip().split('\n') if line.strip()]
                count_saved = 0
                affected_employees = set()

                ZKLog = env['zk.machine.attendance'].sudo()
                RawPunch = env['biometric.raw.punch'].sudo()
                Employee = env['hr.employee'].sudo()

                # Zona horaria del dispositivo
                tz_name = device.device_timezone or 'America/Bogota'
                try:
                    device_tz = pytz.timezone(tz_name)
                except Exception:
                    device_tz = pytz.UTC

                for line in lines:
                    user_pin = None
                    punch_time_str = None
                    punch_status = '0'
                    verify_type = '15' # Default Face

                    parts = line.split('\t')
                    if len(parts) >= 2 and not any('=' in p for p in parts[:2]):
                        user_pin = parts[0].strip()
                        punch_time_str = parts[1].strip()
                        if len(parts) >= 3:
                            punch_status = parts[2].strip()
                        if len(parts) >= 4:
                            verify_type = parts[3].strip()
                    else:
                        # Parseo alternativo por campos clave (PIN= / pin=, TIME= / time=)
                        for part in parts:
                            p_lower = part.lower().strip()
                            if p_lower.startswith('pin='):
                                user_pin = part.split('=', 1)[1].strip()
                            elif p_lower.startswith('time='):
                                punch_time_str = part.split('=', 1)[1].strip()
                            elif p_lower.startswith('inoutstatus=') or p_lower.startswith('status='):
                                punch_status = part.split('=', 1)[1].strip()
                            elif p_lower.startswith('verifytype=') or p_lower.startswith('verify='):
                                verify_type = part.split('=', 1)[1].strip()

                    if not user_pin or not punch_time_str:
                        continue

                    # Parsear fecha y hora
                    try:
                        naive_dt = datetime.strptime(punch_time_str, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        try:
                            naive_dt = datetime.strptime(punch_time_str, '%Y-%m-%d %H:%M')
                        except Exception:
                            continue

                    # Convertir de Zona Horaria del dispositivo a UTC
                    local_dt = device_tz.localize(naive_dt, is_dst=None)
                    utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)

                    # Buscar empleado en Odoo
                    emp = Employee.search([('device_id_num', '=', user_pin)], limit=1)

                    # Verificar si el dispositivo está en la lista de permitidos
                    is_allowed = True
                    if emp and emp.allowed_device_ids and device.id not in emp.allowed_device_ids.ids:
                        is_allowed = False

                    # 1. Guardar en zk.machine.attendance con Hash Idempotente
                    if emp and is_allowed:
                        affected_employees.add(emp.id)
                        hash_key = ZKLog.compute_hash(emp.id, user_pin, utc_dt)
                        if not ZKLog.search_count([('hash_key', '=', hash_key)]):
                            ZKLog.create({
                                'employee_id': emp.id,
                                'device_id_num': user_pin,
                                'punching_time': utc_dt,
                                'punch_type': str(punch_status),
                                'attendance_type': str(verify_type),
                                'address_id': device.address_id.id if device.address_id else False,
                                'source_device_id': device.id,
                                'hash_key': hash_key,
                            })

                    # 2. Guardar en biometric.raw.punch (Auditoría completa)
                    existing_raw = RawPunch.search_count([
                        ('biometric_id', '=', user_pin),
                        ('punch_time', '=', utc_dt),
                        ('device_id', '=', device.id)
                    ])
                    if not existing_raw:
                        partner_id = False
                        if emp:
                            if emp.user_id:
                                partner_id = emp.user_id.partner_id.id
                            elif emp.work_contact_id:
                                partner_id = emp.work_contact_id.id

                        RawPunch.create({
                            'user_id': partner_id,
                            'biometric_id': user_pin,
                            'punch_time': utc_dt,
                            'device_id': device.id,
                            'source': 'zk',
                            'active': True
                        })

                    count_saved += 1

                # Disparar sincronización hacia hr.attendance solo para los empleados que marcaron
                if affected_employees:
                    device._sync_to_hr_attendance(employee_ids=affected_employees)
                device.write({'last_sync_at': fields.Datetime.now()})

                cr.commit()
                return f"OK: {count_saved}"

            # --- CASO 3: Recepción de Fotos Faciales (table=biophoto, userpic, attphoto) ---
            if table.lower() in ('biophoto', 'userpic', 'attphoto'):
                raw_data = request.httprequest.get_data().decode('utf-8', errors='ignore')
                _logger.info(f"ADMS {table} recibido de {sn} (len={len(raw_data)})")
                photos_updated = self._process_biophoto_records(env, sn, device, raw_data)
                cr.commit()
                return f"OK: {photos_updated}"

            # --- CASO 4: Recepción de Registros en Tiempo Real (table=tabledata, user, userinfo) ---
            tablename = (kw.get('tablename') or kw.get('table') or '').lower()
            if table.lower() in ('tabledata', 'user', 'userinfo') or tablename in ('user', 'userinfo', 'userpic', 'biophoto'):
                raw_data = request.httprequest.get_data().decode('utf-8', errors='ignore')
                _logger.info(f"ADMS cdata table={table} tablename={tablename} recibido de {sn} (len={len(raw_data)})")
                if tablename in ('userpic', 'biophoto', 'attphoto') or 'content=' in raw_data.lower():
                    self._process_biophoto_records(env, sn, device, raw_data)
                elif tablename in ('user', 'userinfo') or 'pin=' in raw_data.lower() or 'name=' in raw_data.lower():
                    self._process_user_records(env, sn, device, raw_data)
                cr.commit()
                return "OK"

            # Otros endpoints o confirmación de opciones (rtstate, tabledata, USERINFO, etc.)
            raw_data = request.httprequest.get_data().decode('utf-8', errors='ignore')
            if raw_data:
                _logger.info(f"ADMS cdata table={table} kw={kw} recibido de {sn}:\n{raw_data}")
            cr.commit()
            return "OK"

        except Exception as e:
            _logger.exception(f"ADMS Error procesando /iclock/cdata: {e}")
            if cr:
                cr.rollback()
            return f"ERROR: {e}"
        finally:
            if cr:
                cr.close()

    @http.route('/iclock/getrequest', type='http', auth='none', methods=['GET'], csrf=False)
    def iclock_getrequest(self, **kw):
        """
        Heartbeat periódico del biométrico.
        Sirve para mantener al dispositivo 'En Línea' y entregar comandos encolados (Reboot, Clear, etc.).
        """
        sn = kw.get('SN')
        if not sn:
            return "OK"

        env, cr = self._get_env(kw)
        if not env:
            return "OK"

        try:
            client_ip = self._get_client_ip()
            _logger.debug("ADMS: Heartbeat recibido de SN: %s (IP: %s)", sn, client_ip)
            Device = env['biometric.device.details'].sudo()
            device = Device.search([('sn', '=', sn)], limit=1)

            if not device:
                device = Device.create({
                    'name': f'SpeedFace ({sn})',
                    'sn': sn,
                    'device_ip': client_ip,
                    'status': 'ok',
                    'authorized': False,
                    'protocol_type': 'adms',
                    'last_heartbeat': fields.Datetime.now()
                })
                _logger.info("ADMS: Nuevo biométrico detectado y registrado automáticamente vía Heartbeat (No autorizado por defecto): %s", sn)
            else:
                now_dt = fields.Datetime.now()
                # R1: Actualizar en BD solo si pasaron al menos 60 segundos o si cambió IP/status
                needs_update = (
                    not device.last_heartbeat
                    or (now_dt - device.last_heartbeat).total_seconds() > 60
                    or device.device_ip != client_ip
                    or device.status != 'ok'
                    or bool(device.last_error)
                )
                if needs_update:
                    device.write({
                        'device_ip': client_ip,
                        'last_heartbeat': now_dt,
                        'status': 'ok',
                        'last_error': False
                    })

                # Buscar comandos pendientes para este reloj
                Command = env['biometric.device.command'].sudo()
                pending_cmds = Command.search([
                    ('device_id', '=', device.id),
                    ('state', '=', 'draft')
                ], order='id asc', limit=5)

                if pending_cmds:
                    response_lines = []
                    for cmd in pending_cmds:
                        response_lines.append(f"C:{cmd.id}:{cmd.command}")
                        cmd.write({
                            'state': 'sent',
                            'sent_at': fields.Datetime.now()
                        })
                    cr.commit()
                    return request.make_response("\n".join(response_lines) + "\n", headers=[('Content-Type', 'text/plain')])

            cr.commit()
            return "OK"

        except Exception as e:
            _logger.error(f"ADMS Error en /iclock/getrequest: {e}")
            if cr:
                cr.rollback()
            return "OK"
        finally:
            if cr:
                cr.close()

    @http.route('/iclock/devicecmd', type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def iclock_devicecmd(self, **kw):
        """
        El biométrico confirma la ejecución de un comando encolado.
        Parámetros: ID=<id>&Return=<return_code>&CMD=<cmd>
        """
        sn = kw.get('SN')
        raw = request.httprequest.get_data().decode('utf-8', errors='ignore')

        commands_to_update = []
        if kw.get('ID'):
            commands_to_update.append((kw.get('ID'), kw.get('Return', '0')))

        if raw:
            lines = [l.strip() for l in raw.strip().split('\n') if l.strip()]
            for l in lines:
                c_id = None
                c_ret = '0'
                for part in l.split('&'):
                    if part.startswith('ID='):
                        c_id = part.split('=', 1)[1].strip()
                    elif part.startswith('Return='):
                        c_ret = part.split('=', 1)[1].strip()
                if c_id:
                    commands_to_update.append((c_id, c_ret))

        if commands_to_update:
            env, cr = self._get_env(kw)
            if env:
                try:
                    Command = env['biometric.device.command'].sudo()
                    for cmd_id_str, ret_code in commands_to_update:
                        try:
                            cmd = Command.browse(int(cmd_id_str))
                            if cmd.exists():
                                is_query = bool(cmd.command and 'QUERY' in cmd.command.upper())
                                # Para DATA QUERY, un retorno positivo o 0 indica éxito (número de registros obtenidos)
                                is_success = str(ret_code) == '0' or (is_query and str(ret_code).isdigit() and int(ret_code) >= 0)
                                cmd.write({
                                    'state': 'done' if is_success else 'error',
                                    'return_code': str(ret_code),
                                    'executed_at': fields.Datetime.now()
                                })
                        except Exception as e_cmd:
                            _logger.warning("Error actualizando comando ID %s: %s", cmd_id_str, e_cmd)
                    cr.commit()
                except Exception as e:
                    _logger.error(f"ADMS Error procesando /iclock/devicecmd: {e}")
                    if cr:
                        cr.rollback()
                finally:
                    if cr:
                        cr.close()

        return "OK"

    @http.route('/iclock/registry', type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def iclock_registry(self, **kw):
        """
        Endpoint de registro de dispositivo (ADMS Push v3).
        El terminal envía información de capacidades y parámetros (PushProtVer, DeviceName, etc.)
        y espera confirmación de registro (RegistryCode).
        """
        sn = kw.get('SN')
        raw_body = request.httprequest.get_data().decode('utf-8', errors='ignore')
        _logger.info(f"ADMS: /iclock/registry recibido de SN: {sn}, body: {raw_body}")

        if not sn:
            return "ERROR: Missing SN"

        env, cr = self._get_env(kw)
        if env:
            try:
                Device = env['biometric.device.details'].sudo()
                device = Device.search([('sn', '=', sn)], limit=1)
                client_ip = self._get_client_ip()
                if not device:
                    device = Device.create({
                        'name': f'SpeedFace ({sn})',
                        'sn': sn,
                        'device_ip': client_ip,
                        'status': 'ok',
                        'authorized': False,
                        'protocol_type': 'adms',
                        'last_heartbeat': fields.Datetime.now()
                    })
                    _logger.info(f"ADMS: Dispositivo auto-registrado en registry (No autorizado): {sn}")
                else:
                    device.write({
                        'device_ip': client_ip,
                        'last_heartbeat': fields.Datetime.now(),
                        'status': 'ok',
                        'last_error': False
                    })
                cr.commit()
            except Exception as e:
                _logger.error(f"ADMS Registry error en BD: {e}")
                if cr:
                    cr.rollback()
            finally:
                if cr:
                    cr.close()

        reg_code = hashlib.md5(f"zk_{sn}".encode()).hexdigest()[:16]
        response_txt = (
            f"RegistryCode={reg_code}\n"
            "ServerVersion=3.1.1\n"
            "ServerName=Odoo ADMS\n"
            "PushProtVer=3.1.2\n"
        )
        return request.make_response(response_txt, headers=[('Content-Type', 'text/plain')])

    @http.route('/iclock/push', type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def iclock_push(self, **kw):
        """Endpoint push alternativo usado por algunos firmwares ZK v3."""
        return self.iclock_cdata(**kw)

    def _process_biophoto_records(self, env, sn, device, raw_data):
        """Parsea líneas con fotos faciales biophoto/userpic y las asigna al empleado en Odoo."""
        if not raw_data or not raw_data.strip():
            return 0
        lines = [line.strip() for line in raw_data.strip().split('\n') if line.strip()]
        Employee = env['hr.employee'].sudo()
        photos_updated = 0

        for line in lines:
            parts = line.split('\t')
            kv = {}
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    kv[k.strip().lower()] = v.strip()

            pin = kv.get('pin')
            if not pin and kv.get('filename'):
                pin = kv.get('filename').split('.')[0]
            content = kv.get('content')

            # Fallbacks posicionales si la línea no usó formato clave=valor
            if not pin and len(parts) >= 1 and '=' not in parts[0]:
                pin = parts[0].strip()
            if not content:
                for p in parts:
                    if len(p) > 200:
                        content = p
                        break

            if pin and content:
                pin = pin.strip()
                clean_b64 = content.strip().replace('\r', '').replace('\n', '')
                if clean_b64.startswith('data:'):
                    clean_b64 = clean_b64.split(',', 1)[1]

                emp = Employee.search([('device_id_num', '=', pin)], limit=1)
                if emp:
                    # Solo actualizar si el empleado no tiene una foto personalizada real ya cargada en Odoo
                    if not emp.has_custom_profile_image():
                        emp.with_context(skip_biometric_sync=True).write({
                            'image_1920': clean_b64
                        })
                        photos_updated += 1
                        _logger.info(
                            "ADMS: Foto de perfil asignada a empleado %s (PIN: %s) desde biométrico %s (%s)",
                            emp.name, pin, device.name if device else 'N/A', sn
                        )
                    else:
                        _logger.info(
                            "ADMS: Foto recibida para empleado %s (PIN: %s), pero ya tiene foto personalizada en Odoo.",
                            emp.name, pin
                        )
                else:
                    _logger.info(
                        "ADMS: Foto recibida para PIN %s pero no existe empleado con ese ID biométrico en Odoo.",
                        pin
                    )

        return photos_updated

    def _process_user_records(self, env, sn, device, raw_data):
        """Parsea líneas con usuarios enviadas por DATA QUERY o cdata tabledata y actualiza mapeos."""
        if not raw_data or not raw_data.strip():
            return 0
        lines = [line.strip() for line in raw_data.strip().split('\n') if line.strip()]
        Employee = env['hr.employee'].sudo()
        Mapping = env['biometric.user.mapping'].sudo()
        users_processed = 0
        incoming_pins = set()

        for line in lines:
            parts = line.split('\t')
            kv = {}
            for p in parts:
                if '=' in p:
                    k, v = p.split('=', 1)
                    kv[k.strip().lower()] = v.strip()

            pin = kv.get('pin')
            name = kv.get('name') or kv.get('username') or kv.get('name1')
            if not pin and len(parts) >= 1 and '=' not in parts[0]:
                pin = parts[0].strip()
                if len(parts) >= 2 and '=' not in parts[1]:
                    name = parts[1].strip()

            if pin:
                pin = pin.strip()
                incoming_pins.add(pin)

                # 1. Buscar empleado existente en Odoo por PIN
                emp = Employee.search([('device_id_num', '=', pin)], limit=1)

                # 2. Upsert en biometric.user.mapping para este dispositivo
                if device:
                    mapping = Mapping.search([
                        ('device_id', '=', device.id),
                        ('device_user_id', '=', pin)
                    ], limit=1)

                    real_name = name or (emp.name if emp else f"Usuario {pin}")
                    mapping_vals = {
                        'device_user_name': real_name,
                        'employee_id': emp.id if emp else False,
                        'status': 'mapped' if emp else 'unmapped',
                    }
                    if mapping:
                        mapping.write(mapping_vals)
                    else:
                        mapping_vals.update({
                            'device_id': device.id,
                            'device_user_id': pin,
                        })
                        Mapping.create(mapping_vals)

                users_processed += 1

        return users_processed

    @http.route('/iclock/querydata', type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def iclock_querydata(self, **kw):
        """
        Recepción de resultados de consultas DATA QUERY desde los biométricos.
        Ej: DATA QUERY tablename=biophoto,fielddesc=*,filter=*
        Parámetros: SN=<sn>&type=tabledata&cmdid=<id>&tablename=<table_name>&count=<records>&packcnt=<total_packets>&packidx=<current_packet>
        """
        sn = kw.get('SN') or kw.get('sn')
        tablename = kw.get('tablename') or kw.get('table') or kw.get('type') or ''
        cmdid = kw.get('cmdid')

        raw_data = request.httprequest.get_data().decode('utf-8', errors='ignore')
        _logger.info(
            "ADMS /iclock/querydata de SN %s: tablename=%s, cmdid=%s, count=%s, pack=%s/%s (len=%s)",
            sn, tablename, cmdid, kw.get('count'), kw.get('packidx'), kw.get('packcnt'), len(raw_data)
        )

        env, cr = self._get_env(kw)
        if not env:
            return request.make_response("OK\n", headers=[('Content-Type', 'text/plain')])

        try:
            Device = env['biometric.device.details'].sudo()
            device = Device.search([('sn', '=', sn)], limit=1) if sn else None

            # Si es tabla de fotos faciales (biophoto, userpic, attphoto)
            if tablename.lower() in ('biophoto', 'userpic', 'attphoto') or 'content=' in raw_data.lower():
                count = self._process_biophoto_records(env, sn, device, raw_data)
                _logger.info("ADMS QUERYDATA biophoto: %s foto(s) procesadas para SN %s", count, sn)

            # Si es tabla de usuarios (user, userinfo)
            elif tablename.lower() in ('user', 'userinfo'):
                count = self._process_user_records(env, sn, device, raw_data)
                _logger.info("ADMS QUERYDATA user: %s usuario(s) procesados para SN %s", count, sn)

            cr.commit()
            return request.make_response("OK\n", headers=[('Content-Type', 'text/plain')])

        except Exception as e:
            _logger.exception("ADMS Error procesando /iclock/querydata: %s", e)
            if cr:
                cr.rollback()
            return request.make_response("OK\n", headers=[('Content-Type', 'text/plain')])
        finally:
            if cr:
                cr.close()

    @http.route('/iclock/fdata', type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def iclock_fdata(self, **kw):
        """
        Recepción de archivos binarios/fotos faciales directas desde el biométrico.
        """
        sn = kw.get('SN') or kw.get('sn')
        body = request.httprequest.get_data()
        _logger.info("ADMS /iclock/fdata de SN %s: kw=%s, body_len=%s", sn, kw, len(body))

        if body.startswith(b'\xff\xd8'):  # JPEG magic bytes
            pin = kw.get('PIN') or kw.get('Pin') or kw.get('pin')
            if not pin and kw.get('FileName'):
                pin = kw.get('FileName').split('.')[0]
            if pin:
                import base64
                env, cr = self._get_env(kw)
                if env:
                    try:
                        Employee = env['hr.employee'].sudo()
                        emp = Employee.search([('device_id_num', '=', str(pin).strip())], limit=1)
                        if emp and not emp.has_custom_profile_image():
                            b64 = base64.b64encode(body).decode('utf-8')
                            emp.with_context(skip_biometric_sync=True).write({'image_1920': b64})
                            _logger.info("ADMS FDATA: Foto binaria guardada para empleado %s (PIN: %s)", emp.name, pin)
                        cr.commit()
                    except Exception as e:
                        _logger.exception("ADMS Error procesando /iclock/fdata: %s", e)
                        if cr:
                            cr.rollback()
                    finally:
                        if cr:
                            cr.close()

        return request.make_response("OK\n", headers=[('Content-Type', 'text/plain')])


