# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_config_id = fields.Many2one(
        comodel_name='purchase.approval.setting', 
        string='Grupo Aprobador',
    )

    state = fields.Selection(
        selection_add=[
            ("in approval", "En Aprobación"),
            ("approval_without_budget", "En Aprobación por presupuesto"),
            ("refused","Rechazado"),
        ],ondelete={
            "in approval": "set default",
            "approval_without_budget": "set default",
            "refused": "set default"
        },
    )
    user_status_budget = fields.Selection(
        selection=[
            ('new', 'New'),
            ('pending', 'Por Aprobar'),
            ('approved', 'Aprobado'),
            ('refused', 'Rechazado')
        ], 
        compute='_compute_user_status_budget',
        string='Estado Usuario',
    )
    
    user_approvals_by_budget_am = fields.Many2many(
        comodel_name='res.users',
        relation='account_move_user_rel',
        column1='move_id',
        column2='user_id',
        string='Aprobadores por falta de presupuesto',
        copy=False
    )
 
    approval_by_budget = fields.Boolean(
        string='Aprobar por Presupuesto',
        default=False,
        copy=False
    )
    approval_by_budget_confirm = fields.Boolean(
        string='Aprobado por Presupuesto',
        default=False,
        copy=False
    )
    reason_approval_by_budget = fields.Char(
        string='Razón de Aprobación por Falta de Presupuesto',
        copy=False
    )

    has_purchase_order_line = fields.Boolean(
        compute="_compute_has_purchase_order_line",
        store=False
    ) # If the invoice doesn't come from a purchase
    
    @api.depends('invoice_line_ids.purchase_line_id')
    def _compute_has_purchase_order_line(self):
        for move in self:
            move.has_purchase_order_line = any(
                line.purchase_line_id for line in move.invoice_line_ids
            )

    @api.depends_context('uid')
    @api.depends('approval_by_budget', 'user_approvals_by_budget_am', 'state')
    def _compute_user_status_budget(self):
        for record in self:
            record.user_status_budget = 'new'
            if (record.approval_by_budget is True and record.state == 'approval_without_budget'
                    and self.env.user.id in record.user_approvals_by_budget_am.ids):
                record.user_status_budget = 'pending'


    def action_request_draft(self):
        self.write({'state': 'draft'})
        self.user_approvals_by_budget_am = [(5, 0, 0)]
        self.approval_by_budget_confirm = False
        return {}

    def action_approve_budget(self):
        self.ensure_one()
        wizard = self.env['purchase.appoval.reason.budget.wizard'].create({'move_id': self.id})
        return {
                'type': 'ir.actions.act_window',
                'name': 'Aprobar por falta de presupuesto',
                'res_model': 'purchase.appoval.reason.budget.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new',
                'context': dict(self.env.context, actual_model='account.move'),
            }

    def action_refuse_budget(self):
        for record in self:
            if self.env.user.id in record.user_approvals_by_budget_am.ids:
                record.write({'state': 'refused'})

    def button_cancel(self):
        res = super(AccountMove, self).button_cancel()
        for order in self:
            if any(move.state not in  ('draft', 'refused') for move in self):
                raise UserError(_("Only draft, approval_without or refused entries can be cancelled."))
            order.user_approvals_by_budget_am = [(5, 0, 0)]
            order.approval_by_budget_confirm = False
        return res

    def button_request_approval_without_budget(self):
        for order in self:
            if order.state not in ['draft', 'sent', 'approved']:
                continue

            if not order.line_ids:
                raise UserError(_("Registre línea(s) de factura antes de continuar."))
            
            if self.env.company.pr_approval_po:
                if not order.approval_config_id.user_approvals_by_budget_am:
                    raise ValidationError('El grupo aprobador {name} no tiene '
                                          'configurados aprobadores por falta de presupuesto para facturas.'.format(name=order.approval_config_id.name))
                order.user_approvals_by_budget_am = order.approval_config_id.user_approvals_by_budget_am
                order.state = 'approval_without_budget'
                order.approval_by_budget = True
                order.action_create_approval_budget_activity()
    
    def action_post(self):
        for move in self:

            if not move.line_ids:
                raise UserError(_("Registre línea(s) de factura antes de continuar."))

            # If the invoice doesn't come from a purchase
            if move.move_type == "in_invoice" and not move.has_purchase_order_line:
                if self.env.company.purchase_budget_controll:
                    if not self.invoice_date:
                        raise UserError(_("Ingrese la fecha de la factura antes de continuar.")) 
                    move.line_ids._get_budget_data()

                    validation = move.check_available_budget()

                    if validation is not True:
                        return validation 

        return super(AccountMove, self).action_post()
            
    @api.depends('restrict_mode_hash_table', 'state', 'inalterable_hash')
    def _compute_show_reset_to_draft_button(self):
        super()._compute_show_reset_to_draft_button()

        for move in self:
            if (
                not self._is_move_restricted(move)
                and not move.inalterable_hash
                and move.state in ('refused','approval_without_budget')
            ):
                move.show_reset_to_draft_button = True


    def action_create_approval_budget_activity(self):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for order in self:
            for user in order.user_approvals_by_budget_am:
                order.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary="Confirmar la factura por falta de presupuesto",
                    note=f"Por favor, revisa y apruebe la factura {order.name}.",
                    user_id=user.id
                )

    def validate_pending_orders_to_approval(self):
        pending_invoices = []

        for account_move in self.search([]):
            if (account_move.user_status_budget == 'pending'
                    and self.env.user.id in account_move.user_approvals_by_budget_am.ids):
                pending_invoices.append(account_move.id)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Mis Aprobaciones',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pending_invoices)],
        }
    
    def button_draft(self):
        for order in self:
            order.user_approvals_by_budget_am = [(5, 0, 0)]
            order.approval_by_budget_confirm = False

            # To 
            refused_moves = self.filtered(lambda m: m.state in ('refused','approval_without_budget'))
            refused_moves.write({'state': 'cancel'})

            return super(AccountMove, self).button_draft()
            
    
    def button_cancel(self):
        res = super(AccountMove, self).button_cancel()
        for order in self:
            order.user_approvals_by_budget_am = [(5, 0, 0)]
            order.approval_by_budget_confirm = False
        return res

    def check_available_budget(self):
        if self.approval_by_budget_confirm is True:
            return True
        lines_without_budget = self.env['account.move.line']
        for line in self.line_ids:
            has_available = line.check_available_budget()
            if not has_available:
                lines_without_budget += line
        if lines_without_budget:
            line_vals = []
            for line in lines_without_budget:
                line_vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'account_line_id': line.id
                }))
                wizard = self.env['purchase.approval.budget.wizard'].create({
                    'line_ids': line_vals,
                    'account_line_id': self.id,
                })
            return {
                'type': 'ir.actions.act_window',
                'name': 'Aprobación por falta de presupuesto',
                'res_model': 'purchase.approval.budget.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new'
            }
        return True

    def copy(self, default=None):
        default = default or {}
        default['approval_by_budget_confirm'] = False
        return super().copy(default=default)

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        default_purchase = self.env['purchase.approval.setting'].search([
            ('company_id', '=', self.env.company.id),
            ('is_default_to_purchase', '=', True)
        ], limit=1)
        if default_purchase:
            defaults['approval_config_id'] = default_purchase.id
        return defaults
    
    @api.depends('payment_state', 'state', 'is_move_sent')
    def _compute_status_in_payment(self):
        for move in self:
            if move.state in ('draft', 'cancel'):
                move.status_in_payment = move.state
            elif move.payment_state:
                move.status_in_payment = move.payment_state
            else:
                move.status_in_payment = 'draft'