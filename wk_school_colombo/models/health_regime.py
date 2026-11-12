# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WkSchoolColomboHealthRegime(models.Model):
    """Catálogo configurable de Régimen de salud (SISBEN / EPS).

    Requerimiento (punto 10): la lista de ~44 regímenes oficiales (niveles y
    rangos de SISBEN, más EPS) no debe quedar fija en código -se necesita
    poder agregar más sin tocar código-. Se deja el "code" oficial como un
    campo propio (no como parte del nombre) para poder mostrarlo junto al
    nombre sin perder la referencia al código que entrega la entidad.
    """

    _name = 'wk.school.colombo.health.regime'
    _description = 'Régimen de salud'
    _order = 'sequence, code'

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción", required=True)
    sequence = fields.Integer(default=1)
    active = fields.Boolean(
        'Activo', default=True,
        help="Al desmarcarlo, el régimen de salud deja de estar disponible "
             "para nuevas selecciones, pero los que ya lo usan conservan la "
             "información sin cambios.")

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for regime in self:
            regime.display_name = (
                f"[{regime.code}] {regime.name}" if regime.code else regime.name)
