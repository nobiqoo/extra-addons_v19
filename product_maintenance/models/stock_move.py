# -*- coding: utf-8 -*-

from odoo import api, models, fields
from datetime import date
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = 'stock.move'

    analytic_distribution = fields.Json(
        string='Analytic Distribution'
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic'),
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('analytic_distribution'):
                continue
            repair_id = vals.get('repair_id')
            if repair_id:
                repair = self.env['repair.order'].browse(repair_id)
                distribution = repair._get_account_analytic_distribution()
                if distribution:
                    vals['analytic_distribution'] = distribution
        return super().create(vals_list)

    def _should_apply_maintenance_analytic_to_account(self, account):
        self.ensure_one()
        return bool(account)

    def _get_analytic_distribution(self):
        self.ensure_one()
        return (
            self.analytic_distribution
            or (self.repair_id and self.repair_id._get_account_analytic_distribution())
            or super()._get_analytic_distribution()
        )

    def _get_account_move_line_vals(self):
        res = super()._get_account_move_line_vals()
        distribution = self._get_analytic_distribution()
        if not distribution:
            return res

        for line_vals in res:
            account = self.env['account.account'].browse(line_vals.get('account_id'))
            if self._should_apply_maintenance_analytic_to_account(account):
                line_vals['analytic_distribution'] = distribution
            else:
                line_vals.pop('analytic_distribution', None)
        return res

    def _validate_maintenance_product(self):
        for record in self:
            if record.product_id.qty_available >= 1 or record.product_uom_qty > 1:
                raise ValidationError(
                    'El producto {name} esta marcado como Equipo de Mantenimiento '
                    'y solo puede tener una unidad disponible.'.format(name=self.product_id.name))
