# -*- coding: utf-8 -*-
"""Libera el flag noupdate de TODOS los registros del módulo para que los
ajustes de configuración cargados como datos (conversión de campos texto a
selección, opciones del portal, etiquetas, orden) se apliquen también sobre
bases de datos ya instaladas en cada actualización.

La configuración del cotizador se trata como "config as code": el XML es la
fuente de verdad, por lo que es deseable que `-u` la reaplique.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'website_quotes_safra'
        """
    )
