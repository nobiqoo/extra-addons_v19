# -*- coding: utf-8 -*-
from odoo import fields, models, tools

class DailyAttendance(models.Model):
    _name = 'daily.attendance'
    _description = 'Daily Attendance Report'
    _auto = False
    _order = 'punching_day desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        readonly=True
    )

    device_id_num = fields.Char(
        string='Biometric ID',
        related='employee_id.device_id_num',
        readonly=True,
    )

    punching_day = fields.Date(
        string='Fecha',
        readonly=True
    )

    check_in = fields.Datetime(
        string='Hora de Entrada',
        readonly=True
    )

    check_out = fields.Datetime(
        string='Hora de Salida',
        readonly=True
    )

    address_id = fields.Many2one(
        'res.partner',
        string='Lugar de Trabajo',
        readonly=True
    )

    is_danger = fields.Boolean(
        string='Requiere Revisión',
        readonly=True
    )

    punch_count = fields.Integer(
        string='Punch Count',
        readonly=True
    )

    ignored_count = fields.Integer(
        string='Ignored Count',
        readonly=True
    )

    ignored_punches = fields.Text(
        string='Ignored Punches',
        readonly=True
    )

    def init(self):
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_zk_att_emp_punch 
            ON zk_machine_attendance (employee_id, punching_time);
        """)
        tools.drop_view_if_exists(self.env.cr, 'daily_attendance')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW daily_attendance AS (
                /*
                 * SESSION-BASED GROUPING ALGORITHM (Multi-Shift / Night-Shift Safe)
                 *
                 * Groups punches into sessions. A new session starts whenever there
                 * is a gap of > 9.5 hours between consecutive punches from the same employee.
                 * Acotado a los últimos 90 días para rendimiento óptimo en BD.
                 */
                WITH punches_with_prev AS (
                    SELECT
                        z.id,
                        z.employee_id,
                        z.punching_time,
                        z.address_id,
                        LAG(z.punching_time) OVER (
                            PARTITION BY z.employee_id
                            ORDER BY z.punching_time
                        ) AS prev_punching_time,
                        p.tz AS company_tz
                    FROM zk_machine_attendance z
                    JOIN hr_employee emp ON z.employee_id = emp.id
                    JOIN res_company comp ON emp.company_id = comp.id
                    LEFT JOIN res_partner p ON comp.partner_id = p.id
                    WHERE z.punching_time >= (CURRENT_DATE - INTERVAL '90 days')
                ),
                session_markers AS (
                    SELECT
                        id,
                        employee_id,
                        punching_time,
                        address_id,
                        company_tz,
                        CASE
                            WHEN prev_punching_time IS NULL THEN 1
                            WHEN EXTRACT(EPOCH FROM (punching_time - prev_punching_time)) / 3600.0 > 9.5 THEN 1
                            ELSE 0
                        END AS is_session_start
                    FROM punches_with_prev
                ),
                sessions AS (
                    SELECT
                        id,
                        employee_id,
                        punching_time,
                        address_id,
                        company_tz,
                        SUM(is_session_start) OVER (
                            PARTITION BY employee_id
                            ORDER BY punching_time
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                        ) AS session_id
                    FROM session_markers
                ),
                session_stats AS (
                    SELECT
                        MIN(id) AS id,
                        employee_id,
                        session_id,
                        MIN(company_tz) AS company_tz,
                        MIN(punching_time) AS session_start,
                        MAX(punching_time) AS session_end,
                        MAX(address_id) AS address_id,
                        COUNT(*) AS punch_count
                    FROM sessions
                    GROUP BY employee_id, session_id
                )
                SELECT
                    ss.id AS id,
                    ss.employee_id AS employee_id,
                    DATE(ss.session_start AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(ss.company_tz, 'America/Bogota')) AS punching_day,
                    ss.session_start AS check_in,
                    ss.session_end AS check_out,
                    ss.address_id AS address_id,
                    (ss.punch_count = 1 OR ss.session_start = ss.session_end) AS is_danger,
                    ss.punch_count AS punch_count,
                    GREATEST(0, ss.punch_count - (CASE WHEN ss.session_start = ss.session_end THEN 1 ELSE 2 END)) AS ignored_count,
                    (
                        SELECT STRING_AGG(
                            TO_CHAR(s2.punching_time AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(ss.company_tz, 'America/Bogota'), 'HH24:MI:SS'),
                            ', ' ORDER BY s2.punching_time
                        )
                        FROM sessions s2
                        WHERE s2.employee_id = ss.employee_id
                          AND s2.session_id = ss.session_id
                          AND s2.punching_time > ss.session_start
                          AND s2.punching_time < ss.session_end
                    ) AS ignored_punches
                FROM session_stats ss
            )
        """)
