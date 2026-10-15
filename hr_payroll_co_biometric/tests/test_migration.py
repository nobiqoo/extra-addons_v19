from datetime import datetime

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestBiometricMigration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.partner_id.tz = 'America/Bogota'
        partner = cls.env['res.partner'].create({'name': 'Biometric migration test'})
        cls.employee = cls.env['hr.employee'].create({
            'partner_id': partner.id, 'device_id_num': '99123',
        })
        cls.device = cls.env['biometric.device.details'].create({
            'name': 'Offline test device', 'device_ip': '192.0.2.1',
        })
        cls.shift = cls.env['hr.shift'].create({
            'name': 'Night test', 'code': 'MIG19',
            'hour_from': 22, 'hour_to': 6, 'rest_time': 0,
        })

    def _punches(self):
        return self.env['biometric.raw.punch'].create([
            {'biometric_id': '099123', 'device_id': self.device.id, 'punch_time': timestamp}
            for timestamp in ('2026-09-25 03:00:00', '2026-09-25 11:00:00')
        ])

    def test_import_is_idempotent_and_database_rejects_duplicates(self):
        punches = self._punches()
        punches.action_process_imported_punches()
        punches.action_process_imported_punches()
        logs = self.env['zk.machine.attendance'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(len(logs), 2)
        self.assertEqual(set(punches.mapped('zk_attendance_id').ids), set(logs.ids))
        self.assertEqual(punches.mapped('biometric_id'), ['99123', '99123'])
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.cr.savepoint():
            logs[0].copy()
            self.env.flush_all()

    def test_night_shift_processing_is_idempotent(self):
        self._punches().action_process_imported_punches()
        schedule = self.env['hr.shift.schedule'].create({
            'date_start': '2026-09-24', 'date_end': '2026-09-25',
        })
        line = self.env['hr.shift.schedule.line'].create({
            'schedule_id': schedule.id, 'employee_id': self.employee.id,
            'shift_id': self.shift.id, 'work_date': '2026-09-24',
        })
        self.assertEqual(line.planned_start, datetime(2026, 9, 25, 3))
        self.assertEqual(line.planned_end, datetime(2026, 9, 25, 11))
        line.action_process_attendance()
        record = line.attendance_record_id
        self.assertEqual(record.actual_check_in, line.planned_start)
        self.assertEqual(record.actual_check_out, line.planned_end)
        self.assertEqual(record.worked_hours, 8)
        self.assertEqual(record.attendance_result, 'ok')
        line.action_process_attendance()
        self.assertEqual(line.attendance_record_id, record)
        self.assertEqual(self.env['hr.attendance.record'].search_count([
            ('schedule_line_id', '=', line.id),
        ]), 1)

    def test_weekday_constraint_is_enforced(self):
        values = {'shift_id': self.shift.id, 'weekday': '0', 'hour_from': 8, 'hour_to': 17}
        self.env['hr.shift.weekday.line'].create(values)
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env['hr.shift.weekday.line'].create(values)
            self.env.flush_all()
