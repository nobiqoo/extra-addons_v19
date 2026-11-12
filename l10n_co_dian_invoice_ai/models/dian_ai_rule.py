# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DianAiRule(models.Model):
    _name = 'dian.ai.rule'
    _description = 'Regla aprendida por el agente de causación DIAN'
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char('Regla', compute='_compute_name', store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', 'Compañía', required=True, ondelete='cascade',
        default=lambda self: self.env.company)
    state = fields.Selection(
        [('proposed', 'Propuesta por el agente'),
         ('learned', 'Aprendida'),
         ('rejected', 'Rechazada')],
        'Estado', required=True, default='learned',
        help='El agente solo aplica sin revisión las reglas aprendidas.')
    origin = fields.Selection(
        [('initial', 'Carga inicial'),
         ('agent', 'Ajuste del agente'),
         ('correction', 'Corrección del contador'),
         ('explanation', 'Explicación del contador')],
        'Origen', required=True, default='initial')
    scope = fields.Selection(
        [('partner_product', 'Este proveedor y producto'),
         ('partner', 'Este proveedor'),
         ('product', 'Este producto'),
         ('category', 'Esta categoría'),
         ('company', 'Toda la compañía')],
        'Alcance', required=True, default='partner_product')
    partner_id = fields.Many2one('res.partner', 'Proveedor', check_company=True, index='btree_not_null')
    product_id = fields.Many2one('product.product', 'Producto', check_company=True, index='btree_not_null')
    categ_id = fields.Many2one('product.category', 'Categoría')
    field_name = fields.Selection(
        [('tax', 'Impuesto'), ('account', 'Cuenta'), ('analytic', 'Analítica')],
        'Campo', required=True, default='tax')
    operation = fields.Selection([('add', 'Agregar'), ('remove', 'Quitar')], 'Operación')
    tax_id = fields.Many2one('account.tax', 'Impuesto', check_company=True)
    original_value = fields.Char('Valor original')
    corrected_value = fields.Char('Valor corregido')
    explanation = fields.Text('Explicación')
    user_id = fields.Many2one('res.users', 'Usuario', default=lambda self: self.env.user)
    move_id = fields.Many2one('account.move', 'Factura', check_company=True, ondelete='set null')

    @api.depends('field_name', 'operation', 'tax_id', 'partner_id', 'product_id', 'categ_id', 'scope')
    def _compute_name(self):
        scopes = dict(self._fields['scope'].selection)
        for rule in self:
            subject = rule.tax_id.name or rule.corrected_value or rule.explanation or ''
            operation = dict(self._fields['operation'].selection).get(rule.operation, '')
            target = rule.partner_id.name or rule.product_id.name or rule.categ_id.name or scopes.get(rule.scope)
            rule.name = ' '.join(part for part in (operation, subject[:60], '·', target) if part)

    @api.model
    def _ai_applicable(self, company, partner, product):
        """Learned rules of the company that apply to a vendor and product."""
        rules = self.search([('company_id', '=', company.id), ('state', '=', 'learned')])
        return rules.filtered(lambda rule: rule._ai_applies_to(partner, product))

    def _ai_applies_to(self, partner, product):
        self.ensure_one()
        if self.scope == 'partner_product':
            return self.partner_id == partner and self.product_id == product
        if self.scope == 'partner':
            return self.partner_id == partner
        if self.scope == 'product':
            return self.product_id == product
        if self.scope == 'category':
            return bool(self.categ_id) and product.categ_id.parent_path.startswith(self.categ_id.parent_path)
        return True

    def _ai_serialize(self):
        return [{
            'rule_id': rule.id,
            'scope': rule.scope,
            'field': rule.field_name,
            'operation': rule.operation,
            'tax_id': rule.tax_id.id,
            'tax': rule.tax_id.name,
            'corrected_value': rule.corrected_value,
            'explanation': rule.explanation,
        } for rule in self]
