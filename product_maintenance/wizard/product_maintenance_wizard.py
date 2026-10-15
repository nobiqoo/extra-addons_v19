# -*- coding: utf-8 -*-

from odoo import models, fields
from datetime import date
from odoo.exceptions import ValidationError


class ProductMaintenanceWizard(models.TransientModel):
    _name = 'product.maintenance.wizard'
    _description = 'Producto de Mantenimiento Wizard'

    date_to = fields.Date(
        string='Fecha Final'
    )

    def update_maintenance_details(self):
        for record in self:
            products = self.env['product.maintenance'].search([
                ('id', 'in', self.env.context.get('active_ids', []))
            ])
            for product in products:
                product.maintenance_to_date = record.date_to
                product.action_create_maintenance_detailed()
