# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime


class SaleOrder(models.Model):
    _inherit = "sale.order"

    state = fields.Selection(
        selection_add=[
            ("in_approval", "En Aprobación"),
        ]
    )

    delegation_setting_id = fields.Many2one(
        "sale.delegation.authority.setting",
        string="Matriz Delegación y Autoridad",
        readonly=True,
        copy=False,
    )

    approval_required = fields.Boolean(string="Requiere aprobación", readonly=True, copy=False)
    approval_done = fields.Boolean(string="Aprobación completada", readonly=True, copy=False)
    approval_refused = fields.Boolean(string="Aprobación rechazada", readonly=True, copy=False)

    quotation_send_pending = fields.Boolean(
        string="Envío pendiente por aprobación",
        readonly=True,
        copy=False,
        help="Se marca cuando el usuario intentó 'Enviar cotización' pero quedó bloqueada por aprobaciones.",
    )
    quotation_sent_by_approval = fields.Boolean(string="Enviada automáticamente", readonly=True, copy=False)

    approval_ids = fields.One2many("sale.order.approval", "order_id", string="Aprobaciones", copy=False)

    amount_total_cop_int = fields.Integer(string="Total (COP)", compute="_compute_amount_total_cop_int", store=False)

    def _compute_amount_total_cop_int(self):
        for order in self:
            order.amount_total_cop_int = order._get_amount_total_cop_int()

    def _get_cop_currency(self):
        cop = self.env.ref("base.COP", raise_if_not_found=False)
        if cop:
            return cop
        return self.env["res.currency"].search([("name", "=", "COP")], limit=1)

    def _get_amount_total_cop_int(self):
        self.ensure_one()
        cop = self._get_cop_currency()
        amount = self.amount_total or 0.0
        if cop and self.currency_id and self.currency_id != cop:
            amount = self.currency_id._convert(amount, cop, self.company_id, fields.Date.context_today(self))
        # tarea: "siempre tratado como número entero en COP"
        return int(round(amount))

    def _get_default_delegation_setting(self):
        self.ensure_one()
        Setting = self.env["sale.delegation.authority.setting"].sudo()
        setting = Setting.search(
            [("company_id", "=", self.company_id.id), ("is_default_to_sale", "=", True)],
            limit=1,
        )
        return setting

    def _get_total_smmlv(self, setting):
        self.ensure_one()
        smmlv = int(setting.smmlv_value or 0)
        if smmlv <= 0:
            return 0.0
        return float(self._get_amount_total_cop_int()) / float(smmlv)

    def _get_applicable_matrix_lines(self, setting):
        self.ensure_one()
        total_smmlv = self._get_total_smmlv(setting)
        lines = setting.line_ids.filtered(lambda l: l.active)
        applicable = lines.filtered(lambda l: (l.smmlv_from or 0) <= total_smmlv)
        return applicable.sorted(key=lambda l: (l.sequence, l.id))

    def _clear_previous_approvals(self):
        self.ensure_one()
        if self.approval_ids:
            self.approval_ids.sudo().write({"status": "cancel"})
            self.approval_ids.sudo().unlink()

    def _activity_schedule_for_level(self, approval):
        self.ensure_one()
        todo_xmlid = "mail.mail_activity_data_todo"

        users = []
        if approval.approver_id:
            users.append(approval.approver_id)
        if approval.alternate_approver_id:
            users.append(approval.alternate_approver_id)

        for u in users:
            self.activity_schedule(
                todo_xmlid,
                user_id=u.id,
                summary=_("Aprobar cotización %s") % (self.name or ""),
                note=_("Esta cotización requiere tu aprobación (nivel %s).") % (approval.sequence or ""),
            )

    def _activity_done_for_users(self, users):
        self.ensure_one()
        if not users:
            return
        activities = self.activity_ids.filtered(lambda a: a.user_id in users)
        for act in activities:
            try:
                act.action_feedback(_("Aprobación registrada."))
            except Exception:
                pass

    def _create_approval_flow_if_needed(self):
        self.ensure_one()

        setting = self._get_default_delegation_setting()
        if not setting:
            return False 

        applicable = self._get_applicable_matrix_lines(setting)
        if not applicable:
            return False 

        self.delegation_setting_id = setting.id
        self.approval_required = True
        self.approval_done = False
        self.approval_refused = False

        self._clear_previous_approvals()

        approvals_vals = []
        first = True
        for line in applicable:
            approvals_vals.append({
                "order_id": self.id,
                "sequence": line.sequence,
                "setting_line_id": line.id,
                "approver_id": line.approver_id.id,
                "alternate_approver_id": line.alternate_approver_id.id if line.alternate_approver_id else False,
                "smmlv_from": line.smmlv_from,
                "status": "pending" if first else "waiting",
            })
            first = False

        self.env["sale.order.approval"].sudo().create(approvals_vals)

        if self.state in ("draft", "sent"):
            self.state = "in_approval"

        first_level = self.approval_ids.sorted(key=lambda a: (a.sequence, a.id))[:1]
        if first_level:
            self._activity_schedule_for_level(first_level)

        total_smmlv = self._get_total_smmlv(setting)
        self.message_post(
            body=_(
                "Se inició flujo de aprobación por Matriz de Delegación y Autoridad."
                "Total COP: %s"
                "Equivalente SMMLV: %.2f"
                "Niveles creados: %s.") % (
                    self._get_amount_total_cop_int(),
                    total_smmlv,
                    len(applicable),
                )
        )
        return True

    def _activate_next_level_if_any(self):
        self.ensure_one()
        approvals = self.approval_ids.sorted(key=lambda a: (a.sequence, a.id))
        pending = approvals.filtered(lambda a: a.status == "pending")
        if pending:
            return  

        waiting = approvals.filtered(lambda a: a.status == "waiting")
        if waiting:
            nxt = waiting[:1]
            nxt.sudo().write({"status": "pending"})
            self._activity_schedule_for_level(nxt)

    def _all_levels_approved(self):
        self.ensure_one()
        approvals = self.approval_ids
        if not approvals:
            return True
        return all(a.status == "approved" for a in approvals)

    def _any_level_refused(self):
        self.ensure_one()
        return any(a.status == "refused" for a in self.approval_ids)

    def _finalize_approval_if_done(self):
        self.ensure_one()

        if self._any_level_refused():
            self.approval_refused = True
            self.approval_done = False
            self.state = "draft"  
            return False

        if not self._all_levels_approved():
            return False

        self.approval_done = True
        self.approval_refused = False
        self.quotation_send_pending = False

        if self.state == "in_approval":
            self.state = "draft"
        return True

    def _send_quotation_automatically(self):
        self.ensure_one()

        if self.quotation_sent_by_approval:
            self.quotation_send_pending = False
            return

        template = self.env.ref("sale.email_template_edi_sale", raise_if_not_found=False)
        if not template:
            self.state = "sent"
            self.quotation_send_pending = False
            self.quotation_sent_by_approval = True
            self.message_post(body=_("Aprobaciones completadas. No se encontró plantilla de correo, se marcó como 'Enviada'."))
            return

        template.sudo().send_mail(self.id, force_send=True)

        self.state = "sent"
        self.quotation_send_pending = False
        self.quotation_sent_by_approval = True

        self.message_post(body=_("Aprobaciones completadas. Cotización enviada automáticamente al cliente."))

    def action_quotation_send(self):
        self.ensure_one()

        if self.state == "sent":
            return super().action_quotation_send()

        if self.approval_done and not self.quotation_send_pending:
            return super().action_quotation_send()

        blocked = self._create_approval_flow_if_needed()
        if not blocked:
            return super().action_quotation_send()

        self.quotation_send_pending = True

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Aprobación requerida"),
                "message": _(
                    "Se creó el flujo de aprobaciones. Revisa la pestaña 'Aprobaciones'. "
                    "La cotización se enviará automáticamente al aprobarse todos los niveles."
                ),
                "sticky": False,
                "type": "warning",
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }


class SaleOrderApproval(models.Model):
    _name = "sale.order.approval"
    _description = "Aprobación Cotización (Delegación y Autoridad)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    setting_line_id = fields.Many2one("sale.delegation.authority.line", string="Línea Matriz", readonly=True)

    sequence = fields.Integer(string="Secuencia", readonly=True)
    smmlv_from = fields.Integer(string="A partir de (SMMLV)", readonly=True)

    approver_id = fields.Many2one("res.users", string="Aprobador Principal", readonly=True)
    alternate_approver_id = fields.Many2one("res.users", string="Aprobador Paralelo", readonly=True)

    status = fields.Selection([
        ("new", "Nuevo"),
        ("waiting", "En espera"),
        ("pending", "Pendiente"),
        ("approved", "Aprobado"),
        ("refused", "Rechazado"),
        ("cancel", "Cancelado"),
    ], default="new", tracking=True)

    approved_by_id = fields.Many2one("res.users", string="Aprobado por", readonly=True)
    approved_date = fields.Datetime(string="Fecha de aprobación", readonly=True)

    refused_by_id = fields.Many2one("res.users", string="Rechazado por", readonly=True)
    refused_date = fields.Datetime(string="Fecha de rechazo", readonly=True)

    can_current_user_approve = fields.Boolean(compute="_compute_can_current_user_approve", store=False)

    @api.depends("status", "approver_id", "alternate_approver_id")
    def _compute_can_current_user_approve(self):
        user = self.env.user
        for rec in self:
            rec.can_current_user_approve = (
                rec.status == "pending"
                and (rec.approver_id == user or rec.alternate_approver_id == user)
            )

    def action_approve(self):
        for rec in self:
            rec._check_user_can_act()
            if rec.status != "pending":
                raise UserError(_("Solo puedes aprobar niveles en estado Pendiente."))

            rec.sudo().write({
                "status": "approved",
                "approved_by_id": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            })

            users_done = [u for u in [rec.approver_id, rec.alternate_approver_id] if u]
            rec.order_id._activity_done_for_users(users_done)

            rec.order_id.message_post(body=_(
                "Nivel %s aprobado por %s.") % (rec.sequence, self.env.user.name)
            )

            rec.order_id._activate_next_level_if_any()
            done = rec.order_id._finalize_approval_if_done()
            if done:
                return rec.order_id.action_quotation_send()

    def action_refuse(self):
        for rec in self:
            rec._check_user_can_act()
            if rec.status != "pending":
                raise UserError(_("Solo puedes rechazar niveles en estado Pendiente."))

            rec.sudo().write({
                "status": "refused",
                "refused_by_id": self.env.user.id,
                "refused_date": fields.Datetime.now(),
            })

            waiting = rec.order_id.approval_ids.filtered(lambda a: a.status == "waiting")
            if waiting:
                waiting.sudo().write({"status": "refused"})

            users_done = [u for u in [rec.approver_id, rec.alternate_approver_id] if u]
            rec.order_id._activity_done_for_users(users_done)

            rec.order_id.message_post(body=_(
                "Nivel %s rechazado por %s.") % (rec.sequence, self.env.user.name)
            )

            rec.order_id._finalize_approval_if_done()

    def _check_user_can_act(self):
        user = self.env.user
        for rec in self:
            if rec.approver_id != user and rec.alternate_approver_id != user:
                raise UserError(_("No estás autorizado para aprobar/rechazar este nivel."))
