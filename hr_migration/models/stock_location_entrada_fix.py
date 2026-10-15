# -*- coding: utf-8 -*-

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class StockLocationEntradaFix(models.AbstractModel):
    _name = "stock.location.entrada.fix"
    _description = "Stock Location BOD67/Entrada Migration Fix (upgrade a 19.0)"

    _LOCATION_ID = 1230  # BOD67/Existencias/Entrada (ubicación de entrada oficial de BODEGA 67)
    _TARGET_PARENT_ID = 1228  # BOD67 (vista)

    def _table_exists(self, table_name):
        self.env.cr.execute("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
        """, (table_name,))
        return bool(self.env.cr.fetchone())

    def run_pre_upgrade_fix(self):
        """
        La ubicación "BOD67/Existencias/Entrada" (id 1230) está anidada
        como hija de "BOD67/Existencias" (id 1229) en vez de colgar
        directamente de "BOD67" (id 1228). La regla de stock "COPIA:
        Entrada → Existencias" (pull_push) va de esa ubicación hacia
        Existencias, y como Odoo resuelve las reglas por jerarquía
        (child_of / parent_path) y no por igualdad exacta, Entrada vuelve
        a matchear la misma regla al buscar quién la abastece:
        product._get_rules_from_location entra en bucle infinito y aborta
        la carga del módulo stock con UserError "endless loop: COPIA:
        Entrada → Existencias".

        Este fix respalda el location_id (padre) actual de 1230 y lo
        cambia a 1228 (BOD67) usando el ORM -no SQL crudo-, para que Odoo
        recalcule correctamente parent_path (stock.location usa
        _parent_store) y la jerarquía deje de ser ambigua.
        """
        cr = self.env.cr
        _logger.warning("START STOCK LOCATION ENTRADA PRE-UPGRADE FIX")

        if not self._table_exists("stock_location"):
            _logger.warning("stock_location table not found")
            return

        location = self.env["stock.location"].browse(self._LOCATION_ID).exists()
        if not location:
            _logger.warning("Location %s not found", self._LOCATION_ID)
            return

        cr.execute("""
            CREATE TABLE IF NOT EXISTS stock_location_entrada_parent_backup (
                location_id  integer PRIMARY KEY,
                parent_id    integer,
                backed_up_at timestamp DEFAULT now()
            )
        """)

        cr.execute("""
            INSERT INTO stock_location_entrada_parent_backup (location_id, parent_id)
            VALUES (%s, %s)
            ON CONFLICT (location_id) DO NOTHING
            RETURNING location_id, parent_id
        """, (location.id, location.location_id.id))
        backed_up = cr.fetchall()
        _logger.warning("STOCK LOCATION ENTRADA PRE-UPGRADE FIX backed up: %s", backed_up)

        location.write({"location_id": self._TARGET_PARENT_ID})
        _logger.warning(
            "STOCK LOCATION ENTRADA PRE-UPGRADE FIX -> location_id=%s new_parent_id=%s (complete_name=%s)",
            location.id, self._TARGET_PARENT_ID, location.complete_name,
        )

        cron = self.env.ref("hr_migration.ir_cron_stock_location_entrada_pre_upgrade", raise_if_not_found=False)
        if cron:
            cron.write({"active": False})

        _logger.warning("STOCK LOCATION ENTRADA PRE-UPGRADE FIX FINISHED")

    def run_post_upgrade_restore(self):
        """ 
        Restaura el location_id (padre) original de la ubicación 1230,
        guardado por run_pre_upgrade_fix antes de la actualización.
        """
        cr = self.env.cr
        _logger.warning("START STOCK LOCATION ENTRADA POST-UPGRADE RESTORE")

        if not self._table_exists("stock_location_entrada_parent_backup"):
            _logger.warning("stock_location_entrada_parent_backup table not found")
            return

        cr.execute("""
            SELECT location_id, parent_id
            FROM stock_location_entrada_parent_backup
            WHERE location_id = %s
        """, (self._LOCATION_ID,))
        row = cr.fetchone()
        if not row:
            _logger.warning("No backup found for location %s", self._LOCATION_ID)
            return

        location_id, original_parent_id = row
        location = self.env["stock.location"].browse(location_id).exists()
        if not location:
            _logger.warning("Location %s not found, nothing to restore", location_id)
            return

        location.write({"location_id": original_parent_id})
        _logger.warning(
            "STOCK LOCATION ENTRADA POST-UPGRADE RESTORE -> location_id=%s restored_parent_id=%s (complete_name=%s)",
            location.id, original_parent_id, location.complete_name,
        )

        cron = self.env.ref("hr_migration.ir_cron_stock_location_entrada_post_upgrade", raise_if_not_found=False)
        if cron:
            cron.write({"active": False})

        _logger.warning("STOCK LOCATION ENTRADA POST-UPGRADE RESTORE FINISHED")
