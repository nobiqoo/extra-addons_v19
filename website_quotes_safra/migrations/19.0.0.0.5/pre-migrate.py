# -*- coding: utf-8 -*-
"""Libera el flag noupdate de los registros del módulo para que los ajustes
del Sprint 1 (data/safra_sprint1.xml: reactivación de Exhibición por grupo y
desactivación de Vertical Premium) se apliquen también sobre bases de datos
ya instaladas al actualizar con `-u website_quotes_safra`.

Se ejecuta cuando la versión del manifiesto suba a 19.0.0.0.5 o superior.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'website_quotes_safra'
        """
    )
