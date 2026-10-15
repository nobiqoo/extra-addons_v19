# -*- coding: utf-8 -*-
from odoo import fields, models, tools
from odoo.exceptions import UserError


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

    # Biometric ID (related al empleado)
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

    def unlink(self):
        raise UserError(
            'Attendance Analysis es una vista de consulta y no se puede eliminar. '
            'Si necesita corregir una marcación, hágalo desde las marcaciones '
            'biométricas originales.'
        )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'daily_attendance')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW daily_attendance AS (
                WITH daily_stats AS (
                    SELECT
                        z.employee_id,
                        -- CORRECCION ZONA HORARIA DINAMICA
                        -- Se obtiene la TZ de la compañia del empleado, o America/Bogota por defecto si no esta configurada
                        DATE(z.punching_time AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(p.tz, 'America/Bogota')) AS p_day,
                        MIN(z.punching_time) AS start_time,
                        MAX(z.punching_time) AS end_time
                    FROM zk_machine_attendance z
                    JOIN hr_employee emp ON z.employee_id = emp.id
                    JOIN res_company comp ON emp.company_id = comp.id
                    LEFT JOIN res_partner p ON comp.partner_id = p.id
                    GROUP BY 
                        z.employee_id, 
                        DATE(z.punching_time AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(p.tz, 'America/Bogota'))
                )
                SELECT
                    -- ID único para la vista
                    MIN(z.id) AS id,

                    z.employee_id AS employee_id,
                    ds.p_day AS punching_day,

                    ds.start_time AS check_in,
                    ds.end_time AS check_out,

                    -- Se toma una dirección consistente si existe
                    MAX(z.address_id) AS address_id,

                    -- Reglas de riesgo:
                    -- 1 sola marcación o IN == OUT
                    (
                        COUNT(*) = 1
                        OR ds.start_time = ds.end_time
                    ) AS is_danger,

                    COUNT(*) AS punch_count,

                    -- Conteo de marcaciones intermedias
                    -- (Total menos 2, o cero si son iguales)
                    GREATEST(0, COUNT(*) - (CASE WHEN ds.start_time = ds.end_time THEN 1 ELSE 2 END)) AS ignored_count,

                    -- Lista de timestamps INTERMEDIOS
                    STRING_AGG(
                        CASE
                            WHEN z.punching_time > ds.start_time AND z.punching_time < ds.end_time
                            THEN TO_CHAR(z.punching_time AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(p.tz, 'America/Bogota'), 'HH24:MI:SS')
                            ELSE NULL
                        END,
                        ', ' ORDER BY z.punching_time
                    ) AS ignored_punches

                FROM zk_machine_attendance z
                JOIN hr_employee emp ON z.employee_id = emp.id
                JOIN res_company comp ON emp.company_id = comp.id
                LEFT JOIN res_partner p ON comp.partner_id = p.id
                JOIN daily_stats ds ON (
                    z.employee_id = ds.employee_id
                    AND DATE(z.punching_time AT TIME ZONE 'UTC' AT TIME ZONE COALESCE(p.tz, 'America/Bogota')) = ds.p_day
                )

                GROUP BY
                    z.employee_id,
                    ds.p_day,
                    ds.start_time,
                    ds.end_time
            )
        """)
