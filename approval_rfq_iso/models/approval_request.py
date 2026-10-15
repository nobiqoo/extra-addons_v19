# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def _approval_rfq_iso_normalize_analytic_dist(self, dist):
        dist = dist or {}
        if not isinstance(dist, dict):
            return {}
        return {str(k): round(float(v or 0.0), 6) for k, v in dist.items() if v}

    def _approval_rfq_iso_get_line_analytic_distribution(self, line):
        analytic_dist = getattr(line, 'analytic_distribution', None) or {}
        if not analytic_dist and getattr(line, 'analytic_account_id', False):
            analytic_dist = {line.analytic_account_id.id: 100.0}
        return analytic_dist

    def _approval_rfq_iso_get_seller(self, line):
        seller = line.seller_id or line.product_id.with_company(line.company_id)._select_seller(
            quantity=line.po_uom_qty,
            uom_id=line.product_id.uom_id,
        )
        if not seller:
            raise UserError(_("El producto %s no tiene proveedor.") % (line.product_id.display_name,))
        return seller

    def _approval_rfq_iso_prepare_po_values(self, line, seller, vendor):
        po_vals = line._get_purchase_order_values(vendor)
        po_vals['approval_request_origin_id'] = self.id
        po_vals['origin'] = self.name
        # _get_purchase_order_values reads the stored line.seller_id, which can
        # be stale/empty; take the currency from the seller actually resolved
        # for this line so the RFQ always has one.
        if not po_vals.get('currency_id'):
            po_vals['currency_id'] = seller.currency_id.id or line.company_id.currency_id.id
        if getattr(self, 'project_id', False):
            po_vals['project_id'] = self.project_id.id
        return po_vals

    def _approval_rfq_iso_find_matching_line(self, purchase_order, line, seller_uom, analytic_dist_cmp):
        # Never merge: two approval lines with the same product and cost
        # center can still be different concepts (e.g. "Alquiler equipo"
        # vs "Licencias" vs "Certificado"), and combining them into one
        # summed PO line silently drops every description but the first.
        # Each approval line always gets its own PO line.
        return self.env['purchase.order.line']

    def _approval_rfq_iso_prepare_po_line_values(self, line, seller, vendor, purchase_order, analytic_dist):
        seller_uom = seller.product_uom_id or line.product_id.uom_id
        seller_uom_qty = line.product_uom_id._compute_quantity(line.quantity, seller_uom)
        po_line_vals = self.env['purchase.order.line']._prepare_purchase_order_line(
            line.product_id,
            seller_uom_qty,
            seller_uom,
            line.company_id,
            vendor,
            purchase_order,
        )
        po_line_vals['analytic_distribution'] = analytic_dist
        if getattr(line, 'description', False):
            po_line_vals['name'] = line.description
        return po_line_vals

    def action_create_purchase_orders(self):
        self.ensure_one()
        self.product_line_ids._check_products_vendor()

        purchase_orders_by_key = {}
        created_po_ids = set()

        for line in self.product_line_ids:
            seller = self._approval_rfq_iso_get_seller(line)
            vendor = seller.partner_id
            seller_uom = seller.product_uom_id or line.product_id.uom_id
            analytic_dist = self._approval_rfq_iso_get_line_analytic_distribution(line)
            analytic_dist_cmp = self._approval_rfq_iso_normalize_analytic_dist(analytic_dist)

            key = (
                line.company_id.id,
                vendor.id,
                seller.currency_id.id,
                getattr(getattr(self, 'project_id', False), 'id', False),
            )
            purchase_order = purchase_orders_by_key.get(key)
            if not purchase_order:
                purchase_order = self.env['purchase.order'].create(
                    self._approval_rfq_iso_prepare_po_values(line, seller, vendor)
                )
                purchase_orders_by_key[key] = purchase_order
                created_po_ids.add(purchase_order.id)

            purchase_line = self._approval_rfq_iso_find_matching_line(
                purchase_order,
                line,
                seller_uom,
                analytic_dist_cmp,
            )
            if purchase_line:
                purchase_line.product_qty += line.product_uom_id._compute_quantity(line.quantity, seller_uom)
                if getattr(line, 'description', False) and not purchase_line.name:
                    purchase_line.name = line.description
            else:
                purchase_line = self.env['purchase.order.line'].create(
                    self._approval_rfq_iso_prepare_po_line_values(
                        line,
                        seller,
                        vendor,
                        purchase_order,
                        analytic_dist,
                    )
                )
                purchase_order.order_line = [(4, purchase_line.id)]

            line.purchase_order_line_id = purchase_line.id

        # sudo: this status transition is a normal side effect of the
        # request owner clicking "Crear SdP" on their own approved request,
        # not a manual edit. Without sudo, approval.request.write() blocks
        # it (owners of an approved/pending/refused request may only write
        # request_status='cancel'), even though creating the RFQ is exactly
        # what an approved request owner is meant to be able to do.
        self.sudo().write({'request_status': 'created_po'})

        if 'purchase_order_ids' in self._fields and created_po_ids:
            all_po_ids = set(self.mapped('purchase_order_ids').ids) | created_po_ids
            self.write({'purchase_order_ids': [(6, 0, list(all_po_ids))]})

        if not created_po_ids and not self.mapped('product_line_ids.purchase_order_line_id.order_id'):
            raise UserError(_("No se genero ninguna Orden de Compra."))

        return True

    @api.model
    def _register_hook(self):
        result = super()._register_hook()
        self.__class__.action_create_purchase_orders = ApprovalRequest.action_create_purchase_orders
        return result
