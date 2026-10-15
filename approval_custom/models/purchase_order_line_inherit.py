from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    approval_product_line_id = fields.Many2one(
        'approval.product.line',
        string="Approval Product Line"
    )

    @api.model
    def _prepare_purchase_order_line(self, product, quantity, uom, company, partner_id, purchase_order):
        vals = super()._prepare_purchase_order_line(product, quantity, uom, company, partner_id, purchase_order)

        approval_request = self.env['approval.request'].search([
            ('name', '=', purchase_order.origin)
        ], limit=1)

        if approval_request:
            approval_line = self.env['approval.product.line'].search([
                ('product_id', '=', product.id),
                ('approval_request_id', '=', approval_request.id)
            ], limit=1)

            if approval_line:
                vals['approval_product_line_id'] = approval_line.id
                if approval_line.analytic_distribution:
                    vals['analytic_distribution'] = approval_line.analytic_distribution
                elif approval_line.analytic_account_id:
                    vals['analytic_distribution'] = {approval_line.analytic_account_id.id: 100.0}
        return vals
