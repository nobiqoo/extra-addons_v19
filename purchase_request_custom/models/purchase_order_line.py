from odoo import api, fields, models

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    descripcion = fields.Char(string='Descripción', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            incoming_req_desc = (vals.get('name') or '').strip()
            if incoming_req_desc and not vals.get('descripcion'):
                vals['descripcion'] = incoming_req_desc
            vendor_name = ''
            try:
                order = self.env['purchase.order'].browse(vals.get('order_id')) if vals.get('order_id') else False
                product = self.env['product.product'].browse(vals.get('product_id')) if vals.get('product_id') else False
                if order and product:
                    si = self.env['product.supplierinfo'].search([
                        ('product_tmpl_id', '=', product.product_tmpl_id.id),
                        ('partner_id', '=', order.partner_id.id),
                        ('company_id', 'in', [order.company_id.id, False]),
                    ], limit=1)
                    vendor_name = (si.product_name or '').strip()
            except Exception:
                vendor_name = ''

            if vendor_name:
                vals['name'] = vendor_name
            else:
                prod_name = ''
                if vals.get('product_id'):
                    prod = self.env['product.product'].browse(vals['product_id'])
                    prod_name = (prod.display_name or prod.name or '').strip()
                vals['name'] = prod_name or incoming_req_desc or '/'

        return super().create(vals_list)


    @api.onchange('product_id')
    def _onchange_set_descripcion_as_product_name(self):
        for line in self:
            if line.product_id:
                line.descripcion = line.product_id.display_name or line.product_id.name

    def write(self, vals):
        res = super().write(vals)
        for line in self:
            if not (line.name or '').strip():
                line.name = line.product_id.display_name or line.product_id.name or '/'
        return res