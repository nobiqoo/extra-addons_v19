# -*- coding: utf-8 -*-
from odoo import fields, models

# Claves extra que el reporte de cartera por vendedor agrega al resultado del motor estándar.
EXTRA_KEYS = ('vat', 'city_name', 'salesman_name', 'team_name', 'days_due')


class AccountAgedReceivableSalespersonReportHandler(models.AbstractModel):
    _name = 'account.aged.receivable.salesperson.report.handler'
    _inherit = 'account.aged.receivable.report.handler'
    _description = 'Aged Receivable by Salesperson Custom Handler'

    def _get_salesperson_user_ids(self):
        """Usuarios cuyas facturas puede ver el usuario actual: las propias y, si es líder
        de equipo de ventas (grupo habilitado), las de los miembros de sus equipos."""
        users = self.env.user
        if self.env.user.has_group('account_report.group_manage_team_leaders'):
            teams = self.env['crm.team'].sudo().search([('user_id', '=', self.env.user.id)])
            users |= teams.member_ids
        return users.ids

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options['forced_domain'] = options.get('forced_domain', []) + [
            ('move_id.move_type', 'in', ('out_invoice', 'out_refund')),
            ('move_id.invoice_user_id', 'in', self._get_salesperson_user_ids()),
        ]

    def _report_custom_engine_aged_receivable(self, expressions, options, date_scope, current_groupby,
                                              next_groupby, offset=0, limit=None, warnings=None):
        """Reutiliza el motor estándar de cuentas por cobrar y agrega las columnas del vendedor."""
        result = super()._report_custom_engine_aged_receivable(
            expressions, options, date_scope, current_groupby, next_groupby,
            offset=offset, limit=limit, warnings=warnings)

        if current_groupby == 'id':
            amls = self.env['account.move.line'].sudo().browse([key for key, _vals in result])
            today = fields.Date.context_today(self)
            extra_by_aml = {}
            for aml in amls:
                due = aml.date_maturity or aml.date
                extra_by_aml[aml.id] = {
                    'vat': aml.partner_id.vat or None,
                    'city_name': aml.partner_id.city or None,
                    'salesman_name': aml.move_id.invoice_user_id.name or None,
                    'team_name': aml.move_id.team_id.name or None,
                    'days_due': (today - due).days if due else None,
                }
            for key, vals in result:
                vals.update(extra_by_aml.get(key, dict.fromkeys(EXTRA_KEYS)))
        elif isinstance(result, list):
            for _key, vals in result:
                vals.update(dict.fromkeys(EXTRA_KEYS))
        else:
            result.update(dict.fromkeys(EXTRA_KEYS))
        return result
