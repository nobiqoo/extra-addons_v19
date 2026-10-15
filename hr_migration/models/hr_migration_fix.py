# -*- coding: utf-8 -*-

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class HrMigrationFix(models.AbstractModel):
    _name = "hr.migration.fix"
    _description = "HR Migration Fix"

    def _table_exists(self, table_name):
        self.env.cr.execute("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
        """, (table_name,))
        return bool(self.env.cr.fetchone())

    def run_initial_fix(self):
        cr = self.env.cr
        _logger.warning("START INITIAL FIX")

        if not self._table_exists("hr_employee") or not self._table_exists("hr_contract"):
            _logger.warning("Required tables not found")
            return

        cr.execute("""
            CREATE TABLE IF NOT EXISTS hr_contract_date_start_backup (
                contract_id  integer PRIMARY KEY,
                date_start   date,
                backed_up_at timestamp DEFAULT now()
            )
        """)

        # ------------------------------------------------------------------
        # AUTO FIX 1: colisiones con la fecha de creación del empleado
        # ------------------------------------------------------------------
        _logger.warning("Running AUTO FIX 1 (create_date collisions)")
        cr.execute("""
            WITH candidates AS (
                SELECT
                    e.id AS employee_id,
                    e.create_date::date AS employee_create_date,
                    hc.id AS contract_id,
                    hc.date_start::date AS contract_start_date
                FROM hr_employee e
                JOIN hr_contract hc
                ON hc.employee_id = e.id
                AND hc.state = 'open'
                AND hc.date_start IS NOT NULL
            ),
            risky AS (
                SELECT *
                FROM candidates
                WHERE contract_start_date = employee_create_date
                OR contract_start_date = employee_create_date + 1
            ),
            backup AS (
                INSERT INTO hr_contract_date_start_backup (contract_id, date_start)
                SELECT contract_id, contract_start_date FROM risky
                ON CONFLICT (contract_id) DO NOTHING
            )
            UPDATE hr_contract hc
            SET date_start = (hc.date_start::date - 1)
            FROM risky r
            WHERE hc.id = r.contract_id
            AND hc.date_start::date = r.contract_start_date
            RETURNING hc.id, hc.employee_id, hc.date_start
        """)
        rows = cr.fetchall()
        _logger.warning("AUTO FIX 1 adjusted contracts: %s", len(rows))
        for contract_id, employee_id, new_date_start in rows:
            _logger.warning(
                "AUTO FIX 1 -> employee_id=%s contract_id=%s new_date_start=%s",
                employee_id, contract_id, new_date_start,
            )

        # ------------------------------------------------------------------
        # AUTO FIX 2: colisiones de continuidad entre contratos
        # ------------------------------------------------------------------
        _logger.warning("Running AUTO FIX 2 (continuity collisions)")
        cr.execute("""
            WITH ordered_contracts AS (
                SELECT
                    hc.id,
                    hc.employee_id,
                    hc.state,
                    hc.date_start::date AS date_start,
                    hc.date_end::date AS date_end,
                    LAG(hc.date_end::date) OVER (
                        PARTITION BY hc.employee_id
                        ORDER BY hc.date_start, hc.id
                    ) AS prev_end
                FROM hr_contract hc
                WHERE hc.date_start IS NOT NULL
                AND hc.state IN ('open', 'close')
            ),
            risky AS (
                SELECT *
                FROM ordered_contracts
                WHERE state = 'open'
                AND prev_end IS NOT NULL
                AND (
                        date_start = prev_end
                        OR date_start = prev_end + 1
                )
            ),
            backup AS (
                INSERT INTO hr_contract_date_start_backup (contract_id, date_start)
                SELECT id, date_start FROM risky
                ON CONFLICT (contract_id) DO NOTHING
            )
            UPDATE hr_contract hc
            SET date_start = (hc.date_start::date - 1)
            FROM risky r
            WHERE hc.id = r.id
            AND hc.date_start::date = r.date_start
            RETURNING hc.id, hc.employee_id, hc.date_start
        """)
        rows = cr.fetchall()
        _logger.warning("AUTO FIX 2 adjusted contracts: %s", len(rows))
        for contract_id, employee_id, new_date_start in rows:
            _logger.warning(
                "AUTO FIX 2 -> employee_id=%s contract_id=%s new_date_start=%s",
                employee_id, contract_id, new_date_start,
            )

        _logger.warning("INITIAL FIX FINISHED")

    def restore_original_dates(self):
        """
        Restaura date_start en hr_contract desde hr_contract_date_start_backup,
        el respaldo que run_initial_fix guarda antes de correr AUTO FIX 1 y AUTO FIX 2.
        """
        cr = self.env.cr
        _logger.warning("START RESTORE DATES")

        if not self._table_exists("hr_contract_date_start_backup"):
            _logger.warning("hr_contract_date_start_backup table not found")
            return

        if not self._table_exists("hr_contract"):
            _logger.warning("hr_contract table not found")
            return

        cr.execute("""
            UPDATE hr_contract hc
               SET date_start = b.date_start
              FROM hr_contract_date_start_backup b
             WHERE hc.id = b.contract_id
            RETURNING hc.id, hc.date_start
        """)
        restored = cr.fetchall()
        _logger.warning("RESTORE DATES restored: %s", len(restored))
        for contract_id, date_start in restored:
            _logger.warning(
                "RESTORE DATES -> contract_id=%s date_start=%s",
                contract_id, date_start,
            )

        cron = self.env.ref("hr_migration.ir_cron_hr_restore_dates", raise_if_not_found=False)
        if cron:
            cron.write({"active": False})

        _logger.warning("RESTORE DATES FINISHED")