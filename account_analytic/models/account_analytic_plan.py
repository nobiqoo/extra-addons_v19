# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

from .account_analytic import ANALYTIC_ACCOUNT_TYPES


class AccountAnalyticPlan(models.Model):
    _inherit = 'account.analytic.plan'

    account_accountant_identifier = fields.Boolean(
        string='Identificación Cuenta Contable',
        help='Indica si el plan analítico es utilizado para identificar cuentas contables específicas. '
             'Solo se tiene en cuenta en el plan raíz y aplica a todos sus subplanes.',
        default=False,)
    root_account_accountant_identifier = fields.Boolean(
        string='Identificación Cuenta Contable (heredada)',
        related='root_id.account_accountant_identifier',
        help='Valor heredado del plan raíz.',)
    account_type = fields.Selection(
        selection=ANALYTIC_ACCOUNT_TYPES,
        string='Type',
        help='Tipo usado por las cuentas analíticas de este plan que no tienen tipo propio. '
             'Si está vacío, se toma el del plan superior.',)

    def _get_accountant_account_type(self):
        """Tipo definido en el plan o, si no tiene, en el plan superior más cercano."""
        self.ensure_one()
        plan = self
        while plan:
            if plan.account_type:
                return plan.account_type
            plan = plan.parent_id
        return False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('account_accountant_identifier') and not vals.get('parent_id'):
                existing_plans = self.search([('account_accountant_identifier', '=', True), ('parent_id', '=', False)])
                if existing_plans:
                    raise ValidationError("Solo puede existir un plan analítico con 'Identificación Cuenta Contable' activado.")
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('account_accountant_identifier'):
            existing_plan = self.search([
                ('account_accountant_identifier', '=', True),
                ('parent_id', '=', False),
                ('id', 'not in', self.ids),
            ], limit=1)
            if existing_plan:
                raise ValidationError(f"El plan analítico {existing_plan.name} ya tiene 'Identificación Cuenta Contable' activado. Solo puede existir un plan analítico con esta opción activada.")
        return super().write(vals)
