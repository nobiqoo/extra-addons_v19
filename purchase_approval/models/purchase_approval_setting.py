# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

class PurchaseApprovalSetting(models.Model):
    _name = 'purchase.approval.setting'
    _description = 'Purchase Approval Setting'

    name = fields.Char(
        string='Nombre de Matriz'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda'
    )
    approval_coordinador_id = fields.Many2one(
        comodel_name='res.users', 
        string='Coordinador'
    )
    approval_analyst_ids = fields.Many2many(
        comodel_name='res.users',
        relation='purchase_approval_user_rel',
        column1='purchase_approval_id',
        column2='user_id',
        string='Analistas'
    )
    approval_with_sequence = fields.Boolean(
        string='Aprobación con Secuencia',
        help='En caso de que este marcado los aprobadores deben aprobar en secuencia',
        default=False
    )
    approval_line_ids = fields.One2many(
        comodel_name='purchase.approval.line',
        string='Líneas de Aprobación',
        inverse_name='purchase_approval_id'
    )
    approval_automatic = fields.Boolean(
        string='Confirmación Automatica',
        help='En caso de que este marcado se pasará la orden a confirmado cuando se realicen las aprobaciones',
        default=False
    )
    approval_minimum = fields.Integer(
        string="Aprobadores minimos",
        default=1,
    )
    user_approvals_by_budget = fields.Many2many(
        comodel_name='res.users',
        relation='purchase_setting_user_rel',
        column1='setting_id',
        column2='user_id',
        string='Aprobadores por falta de presupuesto'
    )
    is_default_to_purchase = fields.Boolean(
        string='Usar por defecto en compras',
    )
    has_range_lines = fields.Boolean(
        string='Tiene Líneas de Rango',
        compute='_compute_range_coverage',
    )
    range_coverage_max = fields.Monetary(
        string='Monto Máximo Cubierto por la Matriz',
        compute='_compute_range_coverage',
        currency_field='currency_id',
        help='Tope superior ("Hasta") más alto configurado entre las líneas de tipo Rango. '
             'Una Orden de Compra con un valor mayor a este monto no tendrá aprobador asignado.',
    )

    @api.depends('approval_line_ids.approval_type', 'approval_line_ids.amount_to')
    def _compute_range_coverage(self):
        for setting in self:
            range_lines = setting.approval_line_ids.filtered(lambda l: l.approval_type == 'range')
            setting.has_range_lines = bool(range_lines)
            setting.range_coverage_max = max(range_lines.mapped('amount_to')) if range_lines else 0.0

    @api.constrains("is_default_to_purchase")
    def _check_is_default_to_purchase(self):
        for record in self:
            if record.is_default_to_purchase:
                default_purchase = self.env['purchase.approval.setting'].search([
                    ('id', '!=', record.id),
                    ('company_id', '=', record.company_id.id),
                    ('is_default_to_purchase', '=', True)
                ])
                if default_purchase:
                    raise ValidationError('Ya existe una matriz '
                                          'marcada para usar por '
                                          'defecto en compras. [{name}]'.format(name=default_purchase.name))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_matrix_consistency()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'approval_line_ids' in vals:
            self._check_matrix_consistency()
        return res

    def _check_matrix_consistency(self):
        # Llamado explícitamente después de que create()/write() terminan de
        # aplicar TODOS los comandos del one2many, para validar el estado final
        # una sola vez (no con @api.constrains en la línea hija: Odoo procesa
        # los comandos del one2many uno por uno y eso dispara la validación en
        # estados intermedios inconsistentes, bloqueando guardados legítimos).
        for setting in self:
            lines = setting.approval_line_ids
            types = set(lines.mapped('approval_type'))
            if len(types) > 1:
                selection = dict(lines._fields['approval_type'].selection)
                raise ValidationError(_(
                    'La matriz "%s" combina distintos Tipos de Aprobación (%s). '
                    'Todas las líneas de una misma matriz deben usar el mismo tipo.',
                    setting.name or '',
                    ', '.join(selection.get(t, t) for t in types)
                ))

            range_lines = lines.filtered(lambda l: l.approval_type == 'range')
            if len(range_lines) < 2:
                continue

            currency = setting.currency_id or setting.company_id.currency_id
            digits = currency.decimal_places if currency else 2
            # Rangos "Desde"/"Hasta" se configuran en unidades enteras de moneda
            # (ej. ...19.999.999 / 20.000.000...), aunque la moneda técnicamente
            # admita centavos (p.ej. COP tiene decimal_places=2 en Odoo aunque no
            # circulan centavos). Un peso de diferencia entre rangos consecutivos
            # se considera contiguo, no un hueco.
            increment = 1.0

            ordered = range_lines.sorted(key=lambda l: l.amount_from)
            for previous, current in zip(ordered, ordered[1:]):
                if float_compare(current.amount_from, previous.amount_to, precision_digits=digits) <= 0:
                    raise ValidationError(_(
                        'Existe una superposición de rangos en la matriz "%s": el aprobador "%s" '
                        'cubre hasta %s y el aprobador "%s" inicia desde %s.',
                        setting.name or '',
                        ', '.join(previous.user_ids.mapped('name')),
                        previous.amount_to,
                        ', '.join(current.user_ids.mapped('name')),
                        current.amount_from
                    ))
                if float_compare(current.amount_from - previous.amount_to, increment, precision_digits=digits) > 0:
                    raise ValidationError(_(
                        'Existe un rango de montos sin aprobador asignado en la matriz "%s" '
                        'entre %s y %s. Ajuste los valores "Desde"/"Hasta" para que no queden huecos.',
                        setting.name or '',
                        previous.amount_to,
                        current.amount_from
                    ))
