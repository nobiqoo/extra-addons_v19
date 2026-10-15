"""Execute using odoo-bin shell on the isolated biometric validation database."""
import json
from datetime import datetime

import pytz

from odoo import fields
from odoo.addons.hr_payroll_co_biometric.hooks import post_init_hook

DATABASE = 'biometric_migration19_check_20260924'
PREFIX = 'DEMO BIOMETRICO'
MARKER = 'hr_payroll_co_biometric.demo_seed_v1'

if env.cr.dbname != DATABASE:
    raise RuntimeError('This fixture is restricted to the isolated database: ' + DATABASE)

existing = env['ir.config_parameter'].sudo().get_param(MARKER)
if existing:
    print('Demo already loaded; no records changed.\n' + existing)
else:
    company = env.company
    company.partner_id.tz = 'America/Bogota'
    department = env['hr.department'].create({'name': PREFIX + ' - Operaciones', 'company_id': company.id})
    device = env['biometric.device.details'].create({
        'name': PREFIX + ' - Dispositivo ficticio (sin conexion)',
        'device_ip': '192.0.2.10', 'device_timezone': 'America/Bogota',
        'address_id': company.partner_id.id, 'company_id': company.id,
    })
    # Offline fixture: prevent automatic connections to the dummy endpoint.
    crons = env['ir.cron']
    for xmlid in [
        'hr_zk_attendance.cron_download_data',
        'hr_zk_attendance.ir_cron_biometric_device_check',
        'hr_zk_attendance.ir_cron_biometric_sync_time',
        'hr_payroll_co_biometric.ir_cron_process_attendance',
    ]:
        cron = env.ref(xmlid, raise_if_not_found=False)
        if cron:
            cron.active = False
            crons |= cron

    for code, rate in [('HED', 1.25), ('HEN', 1.75), ('RN', .35), ('HEDF', 2.0)]:
        model = env['hr.overtime.type']
        if not model.search([('code', '=', code), ('company_id', '=', company.id)], limit=1):
            model.create({'name': PREFIX + ' - ' + code, 'code': code, 'category': 'earnings',
                          'rate': rate, 'company_id': company.id})
    post_init_hook(env)
    variable = env['economic.variable'].search([
        ('code', '=', 'MAX_HOURS_WORK'), ('company_id', '=', company.id)], limit=1)
    if not variable:
        variable = env['economic.variable'].create({
            'name': PREFIX + ' - Horas mensuales de ejemplo', 'code': 'MAX_HOURS_WORK', 'company_id': company.id})
    if not env['economic.variable.line'].search([
        ('variable_id', '=', variable.id), ('year', '=', '2026'), ('month', '=', '1')], limit=1):
        env['economic.variable.line'].create({'variable_id': variable.id, 'year': '2026', 'month': '1', 'value': 240})

    shifts = {}
    for key, code, start, end in [('day', 'DEMODIA', 8, 16), ('night', 'DEMONOC', 22, 6)]:
        shifts[key] = env['hr.shift'].create({
            'name': PREFIX + ' - ' + key, 'code': code,
            'hour_from': start, 'hour_to': end, 'rest_time': .5,
            'company_id': company.id,
        })
    schedule = env['hr.shift.schedule'].create({
        'name': PREFIX + ' - Escenarios 24 al 27 septiembre 2026',
        'date_start': '2026-09-24', 'date_end': '2026-09-27',
        'department_id': department.id, 'company_id': company.id,
        'notes': 'Datos ficticios para pruebas. Factores y salario de ejemplo, no configuracion productiva.',
    })
    scenarios = [
        ('Asistencia normal', 'day', '2026-09-24', ['2026-09-24 08:00', '2026-09-24 16:00']),
        ('Tardanza 15 minutos', 'day', '2026-09-24', ['2026-09-24 08:15', '2026-09-24 16:00']),
        ('Tardanza 45 minutos', 'day', '2026-09-24', ['2026-09-24 08:45', '2026-09-24 16:00']),
        ('Salida anticipada', 'day', '2026-09-24', ['2026-09-24 08:00', '2026-09-24 13:00']),
        ('Falta salida', 'day', '2026-09-24', ['2026-09-24 08:00']),
        ('Ausencia total', 'day', '2026-09-24', []),
        ('Extra diurna aplicada', 'day', '2026-09-24', ['2026-09-24 08:00', '2026-09-24 18:00']),
        ('Turno nocturno', 'night', '2026-09-24', ['2026-09-24 22:00', '2026-09-25 06:00']),
        ('Extra nocturna y diurna', 'day', '2026-09-24', ['2026-09-24 08:00', '2026-09-24 20:00']),
        ('Dominical aprobado', 'day', '2026-09-27', ['2026-09-27 08:00', '2026-09-27 16:00']),
    ]
    employees = env['hr.employee']
    contracts = env['hr.contract']
    raw = env['biometric.raw.punch']
    tz = pytz.timezone('America/Bogota')
    for index, (label, shift, day, times) in enumerate(scenarios, 1):
        partner = env['res.partner'].with_context(no_reset_password=True).create({
            'name': '%s %02d - %s' % (PREFIX, index, label), 'vat': '990000%02d' % index})
        employee = env['hr.employee'].create({
            'partner_id': partner.id, 'device_id_num': 'DEMO%03d' % index,
            'department_id': department.id, 'company_id': company.id,
        })
        employees |= employee
        contract = env['hr.contract'].create({
            'employee_id': employee.id, 'state': 'open', 'date_start': '2026-01-01',
            'resource_calendar_id': company.resource_calendar_id.id,
        })
        env['wage.update.history'].create({
            'contract_id': contract.id, 'date': '2026-01-01', 'wage': 2400000})
        contracts |= contract
        env['hr.shift.schedule.line'].create({
            'schedule_id': schedule.id, 'employee_id': employee.id,
            'shift_id': shifts[shift].id, 'work_date': day})
        for local_time in times:
            utc = tz.localize(datetime.strptime(local_time, '%Y-%m-%d %H:%M')).astimezone(pytz.utc).replace(tzinfo=None)
            raw |= env['biometric.raw.punch'].create({
                'employee_id': employee.id, 'biometric_id': employee.device_id_num,
                'device_id': device.id, 'punch_time': utc, 'source': 'manual'})
    raw.action_process_imported_punches()
    env.flush_all()
    schedule.action_confirm()
    schedule.line_ids.action_process_attendance()
    records = schedule.line_ids.attendance_record_id
    for record in records:
        name = record.employee_id.name
        if 'Extra diurna aplicada' in name:
            record.novelty_ids.action_approve()
            record.novelty_ids.action_apply()
        elif 'Dominical aprobado' in name:
            record.novelty_ids.action_approve()
        elif 'Turno nocturno' in name:
            record.novelty_ids.action_to_review()
    env.flush_all()
    assert len(employees) == 10 and len(records) == 10 and len(raw) == 17
    assert len(raw.zk_attendance_id) == 17
    summary = {
        'database': DATABASE, 'company': company.name, 'schedule_id': schedule.id,
        'schedule': schedule.name, 'employees': len(employees), 'contracts': len(contracts),
        'devices': 1, 'shifts': 2, 'schedule_lines': len(schedule.line_ids),
        'raw_punches': len(raw), 'processed_punches': len(raw.zk_attendance_id),
        'attendance_records': len(records), 'novelties': len(records.novelty_ids),
        'payroll_overtime': len(records.novelty_ids.overtime_id),
        'disabled_crons': crons.ids,
        'results': [{'employee': r.employee_id.name, 'result': r.attendance_result,
                     'novelties': r.novelty_ids.mapped('state')} for r in records],
    }
    serialized = json.dumps(summary, ensure_ascii=False, indent=2)
    env['ir.config_parameter'].sudo().set_param(MARKER, serialized)
    env.cr.commit()
    print(serialized)
