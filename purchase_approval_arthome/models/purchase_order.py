# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import UserError, ValidationError

# Estados en que una alternativa sigue abierta y puede cancelarse
OPEN_ALTERNATIVE_STATES = ['draft', 'sent', 'to approve', 'in approval', 'approval_without_budget', 'approved']
APPROVAL_ACTIVITY_SUMMARIES = ['Confirmar la orden de compra', 'Confirmar la orden de compra por falta de presupuesto']
DECISION_ACTIVITY_XMLID = 'purchase_approval_arthome.mail_activity_type_alternatives_decision'


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _get_open_alternatives(self):
        return self.alternative_po_ids.filtered(
            lambda po: po.state in OPEN_ALTERNATIVE_STATES and po.id not in self.ids)

    def _get_confirmed_alternatives(self):
        return self.alternative_po_ids.filtered(lambda po: po.state == 'purchase' and po.id not in self.ids)

    def _needs_alternatives_decision(self):
        self.ensure_one()
        config = self.approval_config_id
        return bool(
            config.approval_automatic
            and config.ask_alternatives_on_auto_confirm
            and self._get_open_alternatives()
        )

    def _update_state_from_approval(self):
        auto_confirm = self.filtered(
            lambda po: po.approval_status == 'approved' and po.approval_config_id.approval_automatic)
        if auto_confirm:
            auto_confirm.write({'state': 'approved'})
        return super(PurchaseOrder, self - auto_confirm)._update_state_from_approval()

    def action_approve(self):
        res = super().action_approve()
        approved = self.filtered(
            lambda po: po.approval_status == 'approved'
            and po.state == 'approved'
            and po.approval_config_id.approval_automatic
        )
        pending_decision = approved.filtered(lambda po: po._needs_alternatives_decision())
        if pending_decision:
            pending_decision._log_alternatives_pending_decision()
            pending_decision._schedule_alternatives_decision_activity()
            return pending_decision.button_confirm()
        failed = (approved - pending_decision)._confirm_after_approval()
        (self - self.browse(list(failed)))._log_alternatives_summary()
        if failed:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Automatic confirmation failed"),
                    'message': '\n'.join(failed.values()),
                    'type': 'warning',
                    'sticky': True,
                    'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
                },
            }
        return res

    def _confirm_after_approval(self):
        failed = {}
        for order in self:
            try:
                with self.env.cr.savepoint():
                    order.order_line._validate_analytic_distribution()
                    order._add_supplier_to_product()
                    order.button_approve()
            except (UserError, ValidationError) as error:
                failed[order.id] = _("%(order)s stays Approved: %(reason)s", order=order.name, reason=error.args[0])
                continue
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
        confirmed = self.filtered(lambda po: po.id not in failed)
        if confirmed:
            confirmed._message_log_batch({order.id: _("Order automatically confirmed after approval.") for order in confirmed})
        if failed:
            self.browse(list(failed))._message_log_batch(
                {order_id: _("Automatic confirmation failed. %s", reason) for order_id, reason in failed.items()})
        return failed

    def button_confirm(self):
        if not self.env.context.get('skip_alternative_check'):
            alternatives = self._get_open_alternatives()
            if alternatives:
                view = self.env.ref('purchase_requisition.purchase_requisition_alternative_warning_form')
                return {
                    'name': _("What about the alternative Requests for Quotations?"),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'purchase.requisition.alternative.warning',
                    'views': [(view.id, 'form')],
                    'target': 'new',
                    'context': dict(
                        self.env.context,
                        default_alternative_po_ids=alternatives.ids,
                        default_po_ids=self.ids,
                    ),
                }
        res = super().button_confirm()
        self.filtered(lambda po: po.state == 'purchase').sudo().activity_feedback([DECISION_ACTIVITY_XMLID])
        return res

    def _cancel_discarded_alternatives(self, chosen_orders):
        if not self:
            return
        for creator, orders in self.grouped('create_uid').items():
            orders.with_user(creator).sudo().button_cancel()
        decision_type = self.env.ref(DECISION_ACTIVITY_XMLID)
        self.sudo().activity_ids.filtered(
            lambda activity: activity.summary in APPROVAL_ACTIVITY_SUMMARIES
            or activity.activity_type_id == decision_type
        ).unlink()
        bodies = {
            order.id: _(
                "Cancelled by confirmation of the alternative %s",
                ', '.join(chosen_orders.filtered(
                    lambda po: po.purchase_group_id == order.purchase_group_id).mapped('name')),
            )
            for order in self
        }
        self._message_log_batch(bodies)

    def _schedule_alternatives_decision_activity(self):
        decision_type = self.env.ref(DECISION_ACTIVITY_XMLID)
        for order in self.filtered(lambda po: decision_type not in po.activity_ids.activity_type_id):
            order.activity_schedule(
                DECISION_ACTIVITY_XMLID,
                note=_("The order was approved and has open alternative quotations. "
                       "Confirm it to decide whether to cancel or keep them."),
                user_id=(order.user_id or order.create_uid).id,
            )

    def _log_alternatives_pending_decision(self):
        """Registra en el chatter que la confirmación espera la decisión sobre las alternativas."""
        bodies = {
            order.id: _(
                "Approved by %(user)s. Automatic confirmation is waiting for a decision on the open alternatives: %(orders)s",
                user=self.env.user.name,
                orders=', '.join(order._get_open_alternatives().mapped('name')),
            )
            for order in self
        }
        self._message_log_batch(bodies)

    def _log_alternatives_summary(self, cancelled=None):
        """Registra en el chatter de cada orden confirmada lo aplicado sobre sus alternativas."""
        cancelled = cancelled or self.browse()
        bodies = {}
        for order in self.filtered(lambda po: po.state == 'purchase' and po.alternative_po_ids):
            lines = []
            order_cancelled = cancelled & order.alternative_po_ids
            kept = order._get_open_alternatives()
            confirmed = order._get_confirmed_alternatives()
            if order_cancelled:
                lines.append(_("Alternatives cancelled by %(user)s: %(orders)s",
                               user=self.env.user.name, orders=', '.join(order_cancelled.mapped('name'))))
            if kept:
                lines.append(_("Alternatives kept open by %(user)s: %(orders)s",
                               user=self.env.user.name, orders=', '.join(kept.mapped('name'))))
            if confirmed:
                lines.append(_("Warning: these alternatives were already confirmed and were not cancelled: %s",
                               ', '.join(confirmed.mapped('name'))))
            if lines:
                bodies[order.id] = Markup('<br/>').join(lines)
        if bodies:
            self.browse(list(bodies))._message_log_batch(bodies)
