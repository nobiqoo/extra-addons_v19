# -*- coding: utf-8 -*-
"""Libera el flag noupdate de los registros de configuración de ENROLLABLE
para que `data/safra_enrollable_layout.xml` (cargado en la misma actualización)
pueda reordenar y ajustar los campos sobre bases de datos ya instaladas.

Sin esto, los registros creados originalmente con noupdate="1" se saltan en `-u`
aunque un bloque posterior los declare noupdate="0" (comportamiento de Odoo).
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'website_quotes_safra'
           AND (
                name LIKE 'sf_01_%'
                OR name IN (
                    'field_design_print', 'field_design_exterior',
                    'field_atravesar_tela', 'field_print_m2',
                    'field_custom_design', 'field_sequence_name'
                )
           )
        """
    )
