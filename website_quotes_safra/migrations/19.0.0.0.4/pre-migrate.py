# -*- coding: utf-8 -*-
"""Libera el flag noupdate de TODOS los registros del módulo para que el
reordenamiento global de campos según el Excel "matriz_unificada_variables"
(data/safra_matriz_order.xml) se aplique también sobre bases de datos ya
instaladas al actualizar con `-u website_quotes_safra`.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'website_quotes_safra'
        """
    )
