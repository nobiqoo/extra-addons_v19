from odoo import api, fields, models

class PurchaseSelectorConfirmWizard(models.TransientModel):
    _name = "purchase.selector.confirm.wizard"
    _description = "Confirmación para generar Solicitud de Cotización"

    selector_id = fields.Many2one(
        "purchase.selector.wizard",
        string="Selector",
        required=True,
        ondelete="cascade",
    )
    question = fields.Html(
        default="<h4>¿Está seguro de generar la Solicitud de Cotización con los productos seleccionados?</h4>",
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # enlaza automáticamente con el wizard principal
        active_id = self.env.context.get("active_id")
        if active_id:
            res["selector_id"] = active_id
        return res

    def action_confirm(self):
        """Llama al método que ya genera la RFQ/OC en el wizard principal."""
        self.ensure_one()
        return self.selector_id.action_confirm()

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
