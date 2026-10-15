# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountAnalyticPlan(models.Model):
    _inherit = 'account.analytic.plan'

    account_accountant_identifier = fields.Boolean(
        string='Identificación Cuenta Contable',
        help='Indica si el plan analítico es utilizado para identificar cuentas contables específicas.',
        default=False,)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('account_accountant_identifier'):
                existing_plans = self.search([('account_accountant_identifier', '=', True)])
                if existing_plans:
                    raise ValidationError("Solo puede existir un plan analítico con 'Identificación Cuenta Contable' activado.")
        return super().create(vals_list)

    def write(self, vals):
        if 'account_accountant_identifier' in vals and vals['account_accountant_identifier']:
            existing_plan = self.search([('account_accountant_identifier', '=', True), ('id', '!=', self.id)])
            if existing_plan:
                raise ValidationError(f"El plan analítico {existing_plan.name} ya tiene 'Identificación Cuenta Contable' activado. Solo puede existir un plan analítico con esta opción activada.")
        return super().write(vals)

