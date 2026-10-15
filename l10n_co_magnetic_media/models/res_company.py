# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    informant_entity = fields.Integer(
        string='Entidad Informante',
        help='Entidad informante para la generación de los archivos de medios magnéticos. '
             '1 - Informante General '
             '2 - Fiduciarias '
             '3 - Mandatario y/o Administrador Delegado '
             '4 - Consorcio y/o Unión Temporal '
             '5 - Exploración y Explotación de Hidrocarburos, Gases y Minerales '
             '6 - Joint Venture '
             '7 - Gestor en Cuentas en Participación '
             '8 - Convenios de Cooperación con Entidades Públicas',
        default=1,
        required=True)

    @api.constrains('informant_entity')
    def _check_valor_entero(self):
        for record in self:
            if not 1 <= record.informant_entity <= 8:
                raise ValidationError(
                    "El valor de 'Entidad Informante' debe estar entre 1 y 8 según la clasificación establecida.")
