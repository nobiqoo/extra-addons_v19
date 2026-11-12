# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DianAiExplainWizard(models.TransientModel):
    _name = 'dian.ai.explain.wizard'
    _description = 'Explicar al agente de causación DIAN'

    move_id = fields.Many2one('account.move', 'Factura', required=True)
    company_id = fields.Many2one(related='move_id.company_id')
    partner_id = fields.Many2one(related='move_id.partner_id')
    line_id = fields.Many2one(
        'account.move.line', 'Línea', domain="[('move_id', '=', move_id), ('display_type', '=', 'product')]")
    product_id = fields.Many2one(related='line_id.product_id')
    categ_id = fields.Many2one(related='line_id.product_id.categ_id')
    explanation = fields.Text(
        'Explicación', required=True,
        help='Cuál fue el error y cuál es la regla correcta, por ejemplo: a este proveedor no se '
             'le practica ReteIVA porque es gran contribuyente.')
    scope = fields.Selection(
        [('partner_product', 'Este proveedor y producto'),
         ('partner', 'Este proveedor'),
         ('product', 'Este producto'),
         ('category', 'Esta categoría'),
         ('company', 'Toda la compañía')],
        'Alcance', required=True, default='partner')
    operation = fields.Selection([('add', 'Agregar'), ('remove', 'Quitar')], 'Operación sobre el impuesto')
    tax_id = fields.Many2one(
        'account.tax', 'Impuesto',
        domain="[('company_id', '=', company_id), ('type_tax_use', '=', 'purchase')]")

    @api.onchange('line_id')
    def _onchange_line_id(self):
        if self.line_id and self.scope == 'partner':
            self.scope = 'partner_product'

    def action_confirm(self):
        self.ensure_one()
        scope = self.scope
        needs_partner = scope in ('partner_product', 'partner')
        needs_product = scope in ('partner_product', 'product')
        self.env['dian.ai.rule'].create({
            'company_id': self.company_id.id,
            'state': 'learned',
            'origin': 'explanation',
            'scope': scope,
            'partner_id': needs_partner and self.partner_id.id,
            'product_id': needs_product and self.product_id.id,
            'categ_id': scope == 'category' and self.categ_id.id,
            'field_name': 'tax',
            'operation': self.operation,
            'tax_id': self.tax_id.id,
            'explanation': self.explanation,
            'move_id': self.move_id.id,
        })
        self.move_id.message_post(body=self.explanation, subject=self.env._('Explicación al agente'))
        return {'type': 'ir.actions.act_window_close'}
