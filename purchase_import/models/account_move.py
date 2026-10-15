# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    imports_ids = fields.Many2many(
        comodel_name='purchase.import',
        relation='account_move_purchase_import_rel',
        column1='account_move_id',
        column2='purchase_import_id',
        copy=False,
    )
    import_id = fields.Many2one(
        comodel_name='purchase.import',
        compute='_compute_import_id',
        inverse='_inverse_import_id'
    )
    import_type = fields.Selection(
        selection=[
            ('insurance', 'Insurance'),
            ('freight', 'Freight'),
            ('tariff', 'Tariff'),
            ('tax', 'Taxes'),
            ('expense', 'Expense')
        ],
        copy=False,
    )

    @api.depends('imports_ids')
    def _compute_import_id(self):
        for move in self:
            move.import_id = move.imports_ids and move.imports_ids[0] or False

    def _inverse_import_id(self):
        for move in self:
            if not move.import_id:
                continue
            move.imports_ids |= move.import_id


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    import_type = fields.Selection(
        related='product_id.import_type',
        string='Cost Type',
        store=False,
    )

    @api.constrains('is_landed_costs_line', 'product_id')
    def _check_landed_cost_import_type(self):
        for line in self:
            if line.is_landed_costs_line and not line.product_id.import_type:
                raise ValidationError(
                    _("El producto '%s' debe tener un Tipo de costo definido para usarse como costo en destino.")
                    % line.product_id.display_name
                )
