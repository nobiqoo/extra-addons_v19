from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentOrderRemovePartnersWizard(models.TransientModel):
    _name = "account.payment.order.remove.partners.wizard"
    _description = "Remove partners from payment order"

    order_id = fields.Many2one(
        comodel_name="account.payment.order",
        string="Orden de pago",
        required=True,
        readonly=True,
    )
    available_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="account_payment_order_remove_partners_available_rel",
        column1="wizard_id",
        column2="partner_id",
        compute="_compute_available_partner_ids",
    )
    partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="account_payment_order_remove_partners_selected_rel",
        column1="wizard_id",
        column2="partner_id",
        string="Proveedores a retirar",
        required=True,
        domain="[('id', 'in', available_partner_ids)]",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if (
            not values.get("order_id")
            and self.env.context.get("active_model") == "account.payment.order"
            and self.env.context.get("active_id")
        ):
            values["order_id"] = self.env.context["active_id"]
        return values

    @api.depends("order_id")
    def _compute_available_partner_ids(self):
        for wizard in self:
            wizard.available_partner_ids = wizard.order_id.payment_line_ids.partner_id

    def action_remove_partners(self):
        self.ensure_one()
        order = self.order_id
        if not order:
            raise UserError(_("No se encontró la orden de pago."))
        if order.state != "draft":
            raise UserError(
                _(
                    "Solo puede retirar proveedores cuando la orden de pago "
                    "está en borrador."
                )
            )
        if not self.partner_ids:
            raise UserError(_("Debe seleccionar al menos un proveedor."))

        lines_to_remove = order.payment_line_ids.filtered(
            lambda line: line.partner_id in self.partner_ids
        )
        if not lines_to_remove:
            raise UserError(
                _("No hay líneas de pago para los proveedores seleccionados.")
            )

        line_count = len(lines_to_remove)
        partner_names = list(
            dict.fromkeys(lines_to_remove.mapped("partner_id.display_name"))
        )
        partner_count = len(partner_names)
        lines_to_remove.unlink()

        onchange_method = getattr(order, "_onchange_payment_line_ids", None)
        if onchange_method:
            onchange_method()

        order.message_post(
            body=_(
                "Se retiraron %(partners)s proveedor(es) y %(lines)s línea(s): %(names)s"
            )
            % {
                "partners": partner_count,
                "lines": line_count,
                "names": ", ".join(partner_names),
            }
        )
        return {"type": "ir.actions.act_window_close"}
