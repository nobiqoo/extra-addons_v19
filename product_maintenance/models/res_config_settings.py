# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_native_parts_in_maintenance = fields.Boolean(
        string='Usar proceso de piezas nativo en mantenimiento',
        related='company_id.use_native_parts_in_maintenance',
        readonly=False
    )
    require_product_to_repair_in_maintenance = fields.Boolean(
        string='Requerir producto a reparar en mantenimiento',
        related='company_id.require_product_to_repair_in_maintenance',
        readonly=False
    )
    show_maintenance_tab_in_product_maintenance = fields.Boolean(
        string='Mostrar pestaña de mantenimiento en productos de mantenimiento',
        related='company_id.show_maintenance_tab_in_product_maintenance',
        readonly=False
    )
    use_product_maintenance_in_workcenters = fields.Boolean(
        string='Usar productos de mantenimiento en centros de trabajo',
        related='company_id.use_product_maintenance_in_workcenters',
        readonly=False
    )
    use_product_maintenance_from_manufacturing = fields.Boolean(
        string='Crear órdenes de mantenimiento desde fabricación',
        related='company_id.use_product_maintenance_from_manufacturing',
        readonly=False
    )
    # Integración activos fijos: exigir cuenta analítica en equipos y órdenes de mantenimiento
    require_analytic_in_maintenance = fields.Boolean(
        string='Requerir cuenta analítica en mantenimiento',
        related='company_id.require_analytic_in_maintenance',
        readonly=False
    )
