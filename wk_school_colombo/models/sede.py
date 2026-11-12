# -*- coding: utf-8 -*-
from odoo import fields, models


class WkSchoolColomboSede(models.Model):
    """Catálogo configurable de Sede.

    Reemplaza el uso de company_id (Compañía) como "Sede": el requerimiento
    pedía un campo configurable para Norte/Centro (ampliable a más sedes sin
    tocar código), y usar la Compañía real de Odoo para esto traía
    implicaciones de multi-compañía (contabilidad, almacenes, reglas de
    registro) que no aplican a este concepto, que es puramente descriptivo.
    Mismo patrón mínimo que wk.school.colombo.program.type/class.modality,
    pero sin company_id propio -la Sede ya no depende de la Compañía-.
    """

    _name = 'wk.school.colombo.sede'
    _description = 'Sede'
    _order = 'sequence, name'

    name = fields.Char(string="Nombre", required=True)
    sequence = fields.Integer(default=1)
    active = fields.Boolean(
        'Activo', default=True,
        help="Al desmarcarla, la sede deja de estar disponible para nuevas "
             "selecciones, pero las que ya la usan conservan la información "
             "sin cambios.")
