# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import UserError


class ProfitabilityReportWizard(models.TransientModel):
    _name = 'profitability.report.wizard'
    _description = 'Profitability Report Wizard'

    partner_id = fields.Many2one('res.partner', string='Cliente')
    start_date = fields.Date('Fecha de Inicio', required=True)
    end_date = fields.Date('Fecha Final', required=True)
    category_id = fields.Many2one('product.category', string='Categorías')
    product_id = fields.Many2one('product.product')
    services_included = fields.Boolean(
        string='Incluir Servicios', default=False, help="Incluir productos de tipo servicio en el reporte.")

    def button_generate_report(self):
        profitability_report = self.env['profitability.report']

        partner_id = self.partner_id.id if self.partner_id else None
        start_date = self.start_date
        end_date = self.end_date
        if end_date < start_date:
            raise UserError(
                _("La fecha final no puede ser anterior a la fecha de inicio."))
        category_id = self.category_id.id if self.category_id else None
        product_id = self.product_id.id if self.product_id else None
        services_included = self.services_included

        return profitability_report.generate_report(start_date, end_date, services_included, partner_id, category_id, product_id)
