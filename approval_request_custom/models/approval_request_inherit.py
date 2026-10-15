from odoo import models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ApprovalRequestInherit(models.Model):
    _inherit = 'approval.request'

    def _normalize_analytic_dist(self, dist):
        dist = dist or {}
        if not isinstance(dist, dict):
            return {}
        return {str(k): round(float(v or 0.0), 6) for k, v in dist.items() if v}

    def action_create_purchase_orders(self):
        self.ensure_one()
        self.product_line_ids._check_products_vendor()

        created_po_ids = set()

        for line in self.product_line_ids:
            seller = line.seller_id
            if not seller:
                raise UserError(_("El producto %s no tiene proveedor.") % (line.product_id.display_name,))
            vendor = seller.partner_id
            analytic_dist_raw = getattr(line, 'analytic_distribution', None) or {}

            if not analytic_dist_raw and getattr(line, 'analytic_account_id', False):
                analytic_dist_raw = {line.analytic_account_id.id: 100.0}

            analytic_dist_cmp = self._normalize_analytic_dist(analytic_dist_raw)

            po_domain = line._get_purchase_orders_domain(vendor)
            purchase_orders = self.env['purchase.order'].search(po_domain, limit=1)

            desc = getattr(line, 'description', False)

            if purchase_orders:
                purchase_order = purchase_orders[0]

                if self.project_id and not purchase_order.project_id:
                    purchase_order.project_id = self.project_id.id

                possible_lines = purchase_order.order_line.filtered(
                    lambda l: l.product_id == line.product_id and l.product_uom_id == line.product_uom_id
                )

                purchase_line = False
                for pline in possible_lines:
                    if self._normalize_analytic_dist(pline.analytic_distribution) == analytic_dist_cmp:
                        purchase_line = pline
                        break

                if purchase_line:
                    line.purchase_order_line_id = purchase_line.id
                    purchase_line.product_qty += line.po_uom_qty
                    if desc:
                        defaultish = False
                        try:
                            defaultish = isinstance(purchase_line.name, str) and purchase_line.name.strip().startswith('[')
                        except Exception:
                            defaultish = False
                        if defaultish or not purchase_line.name:
                            purchase_line.name = desc
                else:
                    po_line_vals = self.env['purchase.order.line']._prepare_purchase_order_line(
                        line.product_id,
                        line.quantity,
                        line.product_uom_id,
                        line.company_id,
                        vendor,
                        purchase_order,
                    )

                    po_line_vals['analytic_distribution'] = analytic_dist_raw

                    if desc:
                        po_line_vals['name'] = desc

                    new_po_line = self.env['purchase.order.line'].create(po_line_vals)
                    line.purchase_order_line_id = new_po_line.id
                    purchase_order.order_line = [(4, new_po_line.id)]


                if purchase_order.origin:
                    origins = [o.strip() for o in purchase_order.origin.split(',') if o.strip()]
                    if self.name not in origins:
                        origins.append(self.name)
                        purchase_order.origin = ', '.join(origins)
                else:
                    purchase_order.origin = self.name

                created_po_ids.add(purchase_order.id)

            else:
                po_vals = line._get_purchase_order_values(vendor)
                if self.project_id:
                    po_vals['project_id'] = self.project_id.id

                new_purchase_order = self.env['purchase.order'].create(po_vals)
                created_po_ids.add(new_purchase_order.id)

                po_line_vals = self.env['purchase.order.line']._prepare_purchase_order_line(
                    line.product_id,
                    line.quantity,
                    line.product_uom_id,
                    line.company_id,
                    vendor,
                    new_purchase_order,
                )
                po_line_vals['analytic_distribution'] = analytic_dist_raw

                if desc:
                    po_line_vals['name'] = desc
                new_po_line = self.env['purchase.order.line'].create(po_line_vals)
                line.purchase_order_line_id = new_po_line.id
                new_purchase_order.order_line = [(4, new_po_line.id)]
                new_purchase_order.origin = self.name

        technical_vals = {'request_status': 'created_po'}
        if 'purchase_order_ids' in self._fields and created_po_ids:
            all_po_ids = set(self.mapped('purchase_order_ids').ids) | created_po_ids
            technical_vals['purchase_order_ids'] = [(6, 0, list(all_po_ids))]
        self.sudo().write(technical_vals)

        po_ids = list(created_po_ids) or self.mapped('purchase_order_line_id.order_id.id')
        if not po_ids:
            raise UserError(_("No se generó ninguna Orden de Compra."))
        return True

    @api.model
    def _register_hook(self):
        self.__class__.action_create_purchase_orders = ApprovalRequestInherit.action_create_purchase_orders
