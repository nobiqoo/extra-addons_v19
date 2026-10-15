# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    """Factura o nota de crédito con sede de operación (tarea 10340)."""

    _inherit = 'account.move'

    operation_site_id = fields.Many2one(
        'account.operation.site',
        string="Sede de Operación",
        check_company=True,
        tracking=True,
        help="Sede desde la que se origina el documento. Determina el ReteICA "
             "que se aplica a las líneas: no hace falta conocer la tarifa del "
             "municipio, el sistema la toma del maestro de sedes.")
