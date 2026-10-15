# -*- coding: utf-8 -*-

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class AccountCompanyRelFix(models.AbstractModel):
    _name = "account.company.rel.fix"
    _description = "Account-Company Relation Migration Fix (upgrade a 19.0)"

    def _table_exists(self, table_name):
        self.env.cr.execute("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
        """, (table_name,))
        return bool(self.env.cr.fetchone())

    def run_pre_upgrade_backup_clear(self):
        """
        Respalda el contenido actual de account_account_res_company_rel
        y la vacía. Existe para limpiar filas huérfanas dejadas por un
        intento de upgrade anterior interrumpido (el módulo account
        queda con latest_version desactualizado, así que el propio
        pre-migrate de saas~17.5.1.2 vuelve a intentar insertar pares
        que ya están y falla con "duplicate key ... already exists").
        """
        cr = self.env.cr
        _logger.warning("START ACCOUNT_ACCOUNT_RES_COMPANY_REL PRE-UPGRADE BACKUP+CLEAR")

        if not self._table_exists("account_account_res_company_rel"):
            _logger.warning("account_account_res_company_rel table not found")
            return

        cr.execute("""
            CREATE TABLE IF NOT EXISTS account_account_res_company_rel_backup (
                account_account_id integer NOT NULL,
                res_company_id      integer NOT NULL,
                backed_up_at        timestamp DEFAULT now(),
                PRIMARY KEY (account_account_id, res_company_id)
            )
        """)

        cr.execute("""
            INSERT INTO account_account_res_company_rel_backup
                (account_account_id, res_company_id)
            SELECT account_account_id, res_company_id
              FROM account_account_res_company_rel
            ON CONFLICT (account_account_id, res_company_id) DO NOTHING
            RETURNING account_account_id, res_company_id
        """)
        backed_up = cr.fetchall()
        _logger.warning("ACCOUNT_ACCOUNT_RES_COMPANY_REL PRE-UPGRADE backed up: %s", len(backed_up))
        for account_id, company_id in backed_up:
            _logger.warning(
                "ACCOUNT_ACCOUNT_RES_COMPANY_REL PRE-UPGRADE -> account_id=%s company_id=%s",
                account_id, company_id,
            )

        cr.execute("""
            DELETE FROM account_account_res_company_rel
            RETURNING account_account_id, res_company_id
        """)
        cleared = cr.fetchall()
        _logger.warning("ACCOUNT_ACCOUNT_RES_COMPANY_REL PRE-UPGRADE cleared rows: %s", len(cleared))

        cron = self.env.ref("hr_migration.ir_cron_account_company_rel_pre_upgrade", raise_if_not_found=False)
        if cron:
            cron.write({"active": False})

        _logger.warning("ACCOUNT_ACCOUNT_RES_COMPANY_REL PRE-UPGRADE BACKUP+CLEAR FINISHED")

    def run_post_upgrade_restore(self):
        """
        Restaura en account_account_res_company_rel las filas que
        había guardado run_pre_upgrade_backup_clear.
        """
        cr = self.env.cr
        _logger.warning("START ACCOUNT_ACCOUNT_RES_COMPANY_REL POST-UPGRADE RESTORE")

        if not self._table_exists("account_account_res_company_rel_backup"):
            _logger.warning("account_account_res_company_rel_backup table not found")
            return

        if not self._table_exists("account_account_res_company_rel"):
            _logger.warning("account_account_res_company_rel table not found, nothing to restore into")
            return

        cr.execute("""
            INSERT INTO account_account_res_company_rel
                (account_account_id, res_company_id)
            SELECT account_account_id, res_company_id
              FROM account_account_res_company_rel_backup
            ON CONFLICT (account_account_id, res_company_id) DO NOTHING
            RETURNING account_account_id, res_company_id
        """)
        restored = cr.fetchall()
        _logger.warning("ACCOUNT_ACCOUNT_RES_COMPANY_REL POST-UPGRADE restored: %s", len(restored))
        for account_id, company_id in restored:
            _logger.warning(
                "ACCOUNT_ACCOUNT_RES_COMPANY_REL POST-UPGRADE -> account_id=%s company_id=%s",
                account_id, company_id,
            )

        cron = self.env.ref("hr_migration.ir_cron_account_company_rel_post_upgrade", raise_if_not_found=False)
        if cron:
            cron.write({"active": False})

        _logger.warning("ACCOUNT_ACCOUNT_RES_COMPANY_REL POST-UPGRADE RESTORE FINISHED")
