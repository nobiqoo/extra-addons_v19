# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Sede de operación en los ajustes del punto de venta (tarea 10340).

    En Odoo 19 la caja se configura desde Punto de venta -> Configuración ->
    Ajustes, con el selector "Punto de venta" arriba: los campos con prefijo
    ``pos_`` son related sobre ``pos_config_id`` y se escriben en la caja
    seleccionada.
    """

    _inherit = 'res.config.settings'

    pos_operation_site_id = fields.Many2one(
        'account.operation.site',
        string="Sede de Operación",
        related='pos_config_id.operation_site_id',
        readonly=False)
    pos_reteica_tax_id = fields.Many2one(
        'account.tax',
        string="ReteICA de la sede",
        related='pos_config_id.reteica_tax_id',
        readonly=True)
    pos_has_active_session = fields.Boolean(
        related='pos_config_id.has_active_session')
