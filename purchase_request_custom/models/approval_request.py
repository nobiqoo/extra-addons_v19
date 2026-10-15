from odoo import models, fields, api

class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    fecha_aprobacion = fields.Datetime(string='Fecha de Aprobación', readonly=True)
    ordenes_de_compra_ids = fields.Many2many(
        'purchase.order',
        string='Órdenes de Compra',
        compute='_compute_ordenes_de_compra_ids',
        compute_sudo=True,
        store=False,
        readonly=True,
    )

    def action_confirm(self):
        res = super().action_confirm()
        self.sudo().write({'fecha_aprobacion': fields.Datetime.now()})
        return res

    @api.depends('product_line_ids.product_id', 'name', 'company_id')
    def _compute_ordenes_de_compra_ids(self):
        PurchaseOrder = self.env['purchase.order']
        has_po_m2o = 'approval_request_id' in PurchaseOrder._fields
        has_po_m2m = 'approval_request_ids' in PurchaseOrder._fields

        for rec in self:
            po_rs = PurchaseOrder.browse()

            product_ids = rec.product_line_ids.mapped('product_id').ids
            if not product_ids:
                rec.ordenes_de_compra_ids = po_rs
                continue

            dom = [('order_line.product_id', 'in', product_ids)]
            if has_po_m2o:
                dom += [('approval_request_id', '=', rec.id)]
            elif has_po_m2m:
                dom += [('approval_request_ids', 'in', rec.id)]
            else:
                if rec.name:
                    dom += [('origin', 'ilike', rec.name)]
            if rec.company_id:
                dom += [('company_id', '=', rec.company_id.id)]

            po_rs = PurchaseOrder.search(dom)
            rec.ordenes_de_compra_ids = po_rs
