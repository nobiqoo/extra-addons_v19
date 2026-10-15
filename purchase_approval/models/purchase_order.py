# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_status = fields.Selection(
        selection=[
            ('new', 'Por Enviar'),
            ('pending', 'En aprobación'),
            ('approved', 'Aprobado'),
            ('refused', 'Rechazado'),
            ('cancel', 'Cancelado')
        ], 
        default='new',
        compute = '_compute_approval_status',
        store=True,
        tracking=True,
    )
    approval_ids = fields.One2many(
        comodel_name='purchase.order.approval',
        inverse_name='purchase_order_id',
        string='Aprobadores'
    )
    approval_config_id = fields.Many2one(
        comodel_name='purchase.approval.setting', 
        string='Grupo Aprobador',
    )
    approval_minimum = fields.Integer(
        string="Aprobadores minimos",
        compute='_compute_approval_minimum',
        store=True
    )
    user_status = fields.Selection(
        selection=[
            ('new', 'New'),
            ('pending', 'Por Aprobar'),
            ('waiting', 'Esperando'),
            ('approved', 'Aprobado'),
            ('refused', 'Rechazado'),
            ('cancel', 'Cancelado')
        ], 
        compute='_compute_user_status',
        string='Estado Usuario'
    )
    state = fields.Selection(
        selection_add=[
            ("in approval", "En Aprobación"),
            ("approval_without_budget", "En Aprobación por presupuesto"),
            ("approved", "Aprobado"),
            ("refused","Rechazado"),
        ]
    )
    user_approvals_by_budget = fields.Many2many(
        comodel_name='res.users',
        relation='purchase_order_user_rel',
        column1='order_id',
        column2='user_id',
        string='Aprobadores por falta de presupuesto',
        copy=False
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
    approval_with_sequence = fields.Boolean(
        string='Aprobación con Secuencia',
        help='En caso de que este marcado los aprobadores deben aprobar en secuencia',
        default=False
    )

    @api.depends('approval_ids', 'approval_config_id')
    def _compute_approval_minimum(self):
        for record in self:
            if record.approval_config_id.approval_minimum:
                record.approval_minimum = record.approval_config_id.approval_minimum
            else:
                record.approval_minimum = len(record.approval_ids)

    @api.depends_context('uid')
    @api.depends('approval_ids.status')
    def _compute_user_status(self):
        for record in self:
            record.user_status = 'new'
            for approval in record.approval_ids:
                if self.env.user.id in approval.user_ids.ids:
                    record.user_status = approval.status

    @api.depends_context('uid')
    @api.depends('approval_by_budget', 'user_approvals_by_budget', 'state')
    def _compute_user_status_budget(self):
        for record in self:
            record.user_status_budget = 'new'
            if (record.approval_by_budget is True and record.state == 'approval_without_budget'
                    and self.env.user.id in record.user_approvals_by_budget.ids):
                record.user_status_budget = 'pending'

    @api.depends('approval_ids.status', 'approval_ids.required')
    def _compute_approval_status(self):
        for record in self:
            status_lst = record.mapped('approval_ids.status')
            required_approved = all(a.status == 'approved' for a in record.approval_ids.filtered('required'))
            minimal_approver = record.approval_minimum if len(status_lst) >= record.approval_minimum else len(status_lst)

            if status_lst:
                if status_lst.count('cancel'):
                    status = 'cancel'
                elif status_lst.count('refused'):
                    status = 'refused'
                elif status_lst.count('new'):
                    status = 'new'
                elif status_lst.count('approved') >= minimal_approver and required_approved:
                    status = 'approved'
                else:
                    status = 'pending'
            else:
                status = 'new'
            record.approval_status = status

            if status in ['refused', 'approved']:
                record._update_state_from_approval()

    def _update_state_from_approval(self):
        for record in self:
            if record.approval_status == 'refused':
                record.state = 'refused'
            elif record.approval_status == 'approved':
                if record.approval_config_id.approval_automatic:
                    try:
                        record.order_line._validate_analytic_distribution()
                        record._add_supplier_to_product()

                        record.button_approve()

                        if record.partner_id not in record.message_partner_ids:
                            record.message_subscribe([record.partner_id.id])

                        record.message_post(
                            body=_("Orden confirmada automáticamente tras aprobación."),
                            message_type='notification'
                        )
                    except Exception as e:
                        record.message_post(
                            body=_("Error en confirmación automática: %s. Estado establecido a 'Aprobado'.", str(e)),
                            message_type='warning'
                        )
                        record.state = 'approved'
                else:
                    record.state = 'approved'

    def _ensure_can_approve(self):
        if any(record.user_status == 'waiting' for record in self):
            raise ValidationError(_('No puede aprobar antes que el aprobador del nivel anterior.'))

    def _action_done_approval_activity(self, summary):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for order in self:
            activities = order.activity_ids.filtered(
                lambda activity: (
                    activity.activity_type_id == activity_type
                    and activity.user_id == self.env.user
                    and activity.summary == summary
                )
            )
            activities.sudo().action_feedback()

    def action_approve(self):
        self._ensure_can_approve()

        approver = self.mapped('approval_ids').filtered(
            lambda approver: approver.status == 'pending'
        )

        if self.approval_with_sequence:
            if self.env.user.id in approver.user_ids.ids:
                approver.write({'status': 'approved'})
                self._action_done_approval_activity("Confirmar la orden de compra")

                next_sequence = approver.sequence + 1

                if next_sequence <= self.approval_minimum:
                    approver_next = self.mapped('approval_ids').filtered(
                        lambda approver: approver.status == 'waiting' and approver.sequence == next_sequence
                    )

                    if approver_next:
                        approver_next.write({'status': 'pending'})
                        for user in approver_next.user_ids:
                            self.create_user_activity(user)
        else:
            if self.env.user.id in approver.user_ids.ids:
                for app in approver:
                    if self.env.user.id in app.user_ids.ids:
                        app.write({'status': 'approved'})
                self._action_done_approval_activity("Confirmar la orden de compra")

    def action_refuse(self):
        approver = self.mapped('approval_ids').filtered(
            lambda approver: approver.status == 'pending'
        )

        if self.env.user.id in approver.user_ids.ids:
            approver.write({'status': 'refused'})

        approver_next = self.mapped('approval_ids').filtered(
            lambda approver: approver.status == 'waiting'
        )

        if approver_next:
            approver_next.write({'status': 'refused'})

    def action_request_draft(self):
        if self.env.user.id != self.create_uid.id and self.create_uid.login != '__system__':
            raise UserError(_("La Orden de Compra fue rechazada, únicamente"
                              " el usuario que la creo puede pasarla a estado borrador: {}.".format(self.create_uid.name)))
        self.write({'state': 'draft'})
        self.approval_ids = [(5, 0, 0)]
        self.user_approvals_by_budget = [(5, 0, 0)]
        self.approval_by_budget_confirm = False
        return {}

    def action_approve_budget(self):
        self.ensure_one()
        wizard = self.env['purchase.appoval.reason.budget.wizard'].create({'order_id': self.id})
        return {
                'type': 'ir.actions.act_window',
                'name': 'Aprobar por falta de presupuesto',
                'res_model': 'purchase.appoval.reason.budget.wizard',
                'view_mode': 'form',
                'res_id': wizard.id,
                'target': 'new'
            }

    def action_refuse_budget(self):
        for record in self:
            if self.env.user.id in record.user_approvals_by_budget.ids:
                record.write({'state': 'refused'})

    def button_cancel(self):
        if self.env.user.id != self.create_uid.id and self.create_uid.login != '__system__':
            raise UserError(_("La Orden de Compra puede ser cancelada "
                              "únicamente por el usuario que la creo: {}.".format(self.create_uid.name)))
        res = super(PurchaseOrder, self).button_cancel()
        for order in self:
            order.approval_ids = [(5, 0, 0)]
            order.user_approvals_by_budget = [(5, 0, 0)]
            order.approval_by_budget_confirm = False
        return res

    def button_request_approval(self):
        for order in self:
            if order.state not in ['draft', 'sent']:
                continue

            if not order.order_line:
                raise UserError(_("Registre línea(s) de Orden de Compra antes de continuar."))
            
            # order.order_line._get_budget_data()

            if self.env.company.pr_approval_po:
                order.approval_with_sequence = order.approval_config_id.approval_with_sequence
                approval_ids = order.approval_config_id.approval_line_ids
                sequence = 0
                total_values = []

                for approvers in approval_ids:
                    if self.env.company.currency_id != self.currency_id:
                        amount_currency_total = self.currency_id._convert(
                            self.amount_untaxed, self.env.company.currency_id, self.company_id, fields.Datetime.now()
                        )
                    else:
                        amount_currency_total = self.amount_untaxed

                    if (approvers.approval_type == 'by_amount' and 
                        amount_currency_total >= approvers.amount_from) or approvers.approval_type == 'without_condition':
                        if order.approval_with_sequence:
                            sequence += 1
                        else:
                            sequence = 1

                    if (approvers.approval_type == 'by_amount' and 
                        amount_currency_total >= approvers.amount_from) or approvers.approval_type == 'without_condition':
                        values = {
                            'sequence': sequence,
                            'approval_config_id': self.approval_config_id.id,
                            'company_id': self.env.user.company_id.id,
                            'user_ids': approvers.user_ids,
                            'purchase_order_id': self.id,
                            'required': False,
                            'status': 'pending' if sequence == 1 else 'waiting',
                            'amount_from': approvers.amount_from,
                            'approval_type': approvers.approval_type,
                        }
                        total_values.append((0, 0, values))

                self.approval_ids = total_values
                order.action_create_approval_activity()
                order.write({'state': 'in approval',})

    def button_request_approval_without_budget(self):
        for order in self:
            if order.state not in ['draft', 'sent', 'approved']:
                continue

            if not order.order_line:
                raise UserError(_("Registre línea(s) de Orden de Compra antes de continuar."))
            
            if self.env.company.pr_approval_po:
                if not order.approval_config_id.user_approvals_by_budget:
                    raise ValidationError('El grupo aprobador {name} no tiene '
                                          'configurados aprobadores por falta de presupuesto.'.format(name=order.approval_config_id.name))
                order.user_approvals_by_budget = order.approval_config_id.user_approvals_by_budget
                order.state = 'approval_without_budget'
                order.approval_by_budget = True
                order.action_create_approval_budget_activity()

    def button_confirm(self):
        for order in self:
            if self.env.context.get('skip_approval'):
                super().button_confirm()
                continue
            if order.state not in ['sent','approved'] and self.env.company.pr_approval_po:
                continue

            if order.state != 'approved' and self.env.company.pr_approval_po:
                raise UserError(_("La Orden de Compra no ha sido aprobada aún."))
    
            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()

            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})

            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])

        return True

    def action_create_approval_activity(self):
        for order in self:
            if order.approval_with_sequence:
                if order.approval_ids:
                    approval = order.approval_ids[0]
                    for user in approval.user_ids:
                        order.create_user_activity(user)
            else:
                for approval in order.approval_ids:
                    for user in approval.user_ids:
                        order.create_user_activity(user)

    def create_user_activity(self, user):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        self.activity_schedule(
            activity_type_id=activity_type.id,
            summary="Confirmar la orden de compra",
            note=f"Por favor, revisa y apruebe la orden de compra {self.name}.",
            user_id=user.id
        )

    def action_create_approval_budget_activity(self):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for order in self:
            for user in order.user_approvals_by_budget:
                order.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary="Confirmar la orden de compra por falta de presupuesto",
                    note=f"Por favor, revisa y apruebe la orden de compra {order.name}.",
                    user_id=user.id
                )

    def validate_pending_orders_to_approval(self):
        pending_orders = []

        for purchase_order in self.search([]):
            if purchase_order.user_status == "pending": 
                pending_orders.append(purchase_order.id)
            elif (purchase_order.user_status_budget == 'pending'
                    and self.env.user.id in purchase_order.user_approvals_by_budget.ids):
                pending_orders.append(purchase_order.id)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Mis Aprobaciones',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pending_orders)],
        }

    def check_available_budget(self):
        if self.approval_by_budget_confirm is True:
            return True
        lines_without_budget = self.env['purchase.order.line']
        for line in self.order_line:
            has_available = line.check_available_budget()
            if not has_available:
                lines_without_budget += line
        if lines_without_budget:
            line_vals = []
            for line in lines_without_budget:
                line_vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'order_line_id': line.id
                }))
                wizard = self.env['purchase.approval.budget.wizard'].create({
                    'line_ids': line_vals,
                    'order_id': self.id,
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
