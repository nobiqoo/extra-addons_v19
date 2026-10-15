# -*- coding: utf-8 -*-
"""Devuelve a activos los contratos que nacieron sin el campo ``active``.

La columna ``active`` de ``hr_contract`` viene de la 18.0, pero el modelo de la
19.0 no volvio a declarar el campo hasta la version 19.0.0.0.1. Mientras tanto
el ORM inserto los contratos nuevos sin esa columna y quedaron en NULL, o sea
archivados: no salen en la lista de contratos y la planilla de aportes los
descarta sin avisar aunque sus nominas esten pagadas.

Solo se tocan los NULL: un contrato archivado a proposito queda en FALSE.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("UPDATE hr_contract SET active = TRUE WHERE active IS NULL")
    if cr.rowcount:
        _logger.info("hr_payroll_co: %s contratos sin estado de archivado "
                     "quedan como activos", cr.rowcount)
