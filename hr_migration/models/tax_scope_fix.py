# -*- coding: utf-8 -*-

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class L10nCoTaxScopeFix(models.AbstractModel):
    _name = "l10n.co.tax.scope.fix"
    _description = "L10n CO Tax Scope Migration Fix (upgrade a 19.0)"

    def _table_exists(self, table_name):
        self.env.cr.execute("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
        """, (table_name,))
        return bool(self.env.cr.fetchone())

    def run_pre_upgrade_fix(self):
        """
        Guarda el valor actual de tax_scope de los impuestos l10n_co que
        actúan como hijos de los impuestos de grupo de retención
        (l10n_co_tax_49/50/51/52) y luego lo deja vacío, para que la
        validación _check_children_scope de account_tax.py no aborte la
        actualización cuando el script de migración de l10n_co vuelve a
        crear esos grupos con tax_scope vacío.
        """
        cr = self.env.cr
        _logger.warning("START TAX SCOPE PRE-UPGRADE FIX")

        if not self._table_exists("account_tax"):
            _logger.warning("account_tax table not found")
            return

        cr.execute("""
            CREATE TABLE IF NOT EXISTS l10n_co_tax_scope_backup (
                tax_id        integer PRIMARY KEY,
                tax_scope     varchar,
                backed_up_at  timestamp DEFAULT now()
            )
        """)

        cr.execute("""
            WITH children AS (
                SELECT t.id, t.tax_scope
                FROM ir_model_data d
                JOIN account_tax t ON t.id = d.res_id
                WHERE d.model = 'account.tax'
                  AND d.module = 'account'
                  AND d.name ~ '^[0-9]+_l10n_co_tax_(0|1|12|13|14|15)$'
                  AND t.tax_scope IS NOT NULL
            )
            INSERT INTO l10n_co_tax_scope_backup (tax_id, tax_scope)
            SELECT id, tax_scope FROM children
            ON CONFLICT (tax_id) DO NOTHING
            RETURNING tax_id, tax_scope
        """)
        backed_up = cr.fetchall()
        _logger.warning("TAX SCOPE PRE-UPGRADE FIX backed up: %s", len(backed_up))
        for tax_id, tax_scope in backed_up:
            _logger.warning("TAX SCOPE PRE-UPGRADE FIX -> tax_id=%s tax_scope=%s", tax_id, tax_scope)

        cr.execute("""
            UPDATE account_tax
            SET tax_scope = NULL
            WHERE id IN (SELECT tax_id FROM l10n_co_tax_scope_backup)
            RETURNING id
        """)
        cleared = cr.fetchall()
        _logger.warning("TAX SCOPE PRE-UPGRADE FIX cleared tax_scope on: %s", len(cleared))

        cron = self.env.ref("hr_migration.ir_cron_tax_scope_pre_upgrade", raise_if_not_found=False)
        if cron:
            cron.write({"active": False})

        _logger.warning("TAX SCOPE PRE-UPGRADE FIX FINISHED")

    def run_post_upgrade_restore(self):
        """
        Restaura el valor original de tax_scope guardado por
        run_pre_upgrade_fix antes de la actualización.
        """
        cr = self.env.cr
        _logger.warning("START TAX SCOPE POST-UPGRADE RESTORE")

        if not self._table_exists("l10n_co_tax_scope_backup"):
            _logger.warning("l10n_co_tax_scope_backup table not found")
            return

        cr.execute("""
            UPDATE account_tax t
            SET tax_scope = b.tax_scope
            FROM l10n_co_tax_scope_backup b
            WHERE t.id = b.tax_id
            RETURNING t.id, t.tax_scope
        """)
        restored = cr.fetchall()
        _logger.warning("TAX SCOPE POST-UPGRADE RESTORE restored: %s", len(restored))
        for tax_id, tax_scope in restored:
            _logger.warning("TAX SCOPE POST-UPGRADE RESTORE -> tax_id=%s tax_scope=%s", tax_id, tax_scope)

        cron = self.env.ref("hr_migration.ir_cron_tax_scope_post_upgrade", raise_if_not_found=False)
        if cron:
            cron.write({"active": False})

        _logger.warning("TAX SCOPE POST-UPGRADE RESTORE FINISHED")
