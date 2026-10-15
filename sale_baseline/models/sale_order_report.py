# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import datetime


class SaleOrderReport(models.Model):
    _name = 'sale.order.report'
    _description = 'Sales order and point-of-sale reports'

    pos_reference = fields.Char()
    date = fields.Date('Date')
    order_name = fields.Char('Order Name')
    invoice_name = fields.Char('Invoice Name')
    move_type = fields.Selection([
        ('refund', 'Refund'),
        ('invoice', 'Invoice')
    ])
    default_code = fields.Char('Default Code')
    product_id = fields.Many2one('product.product', 'Product')
    product_template_id = fields.Many2one(
        'product.template', 'Product Template')
    product_detail = fields.Text('Product Detail')
    product_code = fields.Char('Product Code')
    detailed_type = fields.Selection([
        ('consu', 'Consumable'),
        ('service', 'Service'),
        ('product', 'Product')
    ])
    category_id = fields.Many2one('product.category', 'Category')
    product_brand_id = fields.Many2one('product.brand', 'Product Brand')
    uom_id = fields.Many2one('uom.uom', 'UOM')
    quantity_invoiced = fields.Float('Quantity Invoiced')
    price_subtotal = fields.Float('Price Subtotal')
    partner_id = fields.Many2one('res.partner', 'Partner')
    vat = fields.Char('VAT Number')
    city_partner = fields.Char('City')
    state_id = fields.Many2one('res.country.state', 'State')
    team_id = fields.Many2one('crm.team', 'Team')
    user_id = fields.Many2one('res.users', 'Seller')
    state_order = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ])
    state_invoice = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ])

    @api.model
    def prepare_query(self, base_query, start_date, end_date, partner_id=None, category_id=None, product_id=None, so=None):
        params = [start_date, end_date, self.env.company.id]

        if partner_id:
            base_query += " AND rp.id = %s"
            params.append(partner_id)
        if category_id:
            base_query += " AND pc.id = %s"
            params.append(category_id)
        if product_id:
            base_query += " AND pp.id = %s"
            params.append(product_id)
        if so:
            base_query += " ORDER BY aml.id ASC, so.name DESC"
        else:
            base_query += " ORDER BY pos.name DESC"

        return base_query, tuple(params)

    @api.model
    def prepare_query_sale_order(self, start_date, end_date, partner_id=None, category_id=None, product_id=None):
        query = """
            WITH first_supplier AS (
                SELECT
                    psi.product_tmpl_id,
                    psi.product_code,
                    psi.name,
                    ROW_NUMBER() OVER (PARTITION BY psi.product_tmpl_id ORDER BY psi.id) AS rn
                FROM
                    product_supplierinfo psi
            )
            SELECT DISTINCT ON (aml.id)
                am.date AS date,
                so.name AS order_name,
                am.name AS invoice_name,
                CASE
                    WHEN am.move_type = 'out_refund' THEN 'refund'
                    ELSE NULL
                END AS move_type,
                pp.default_code as default_code,
                pp.id AS product_id,
                pt.id AS product_template_id,
                pt.detailed_type AS detailed_type,
                fs.product_code AS product_code,
                pc.id AS category_id,
                pt.product_brand_id AS product_brand_id,
                pt.uom_id AS uom_id,
                CASE
                    WHEN am.move_type = 'out_refund' THEN aml.quantity * (-1)
                    ELSE aml.quantity
                END AS quantity_invoiced,
                CASE
                    WHEN am.move_type = 'out_refund' THEN aml.price_subtotal * (-1)
                    ELSE aml.price_subtotal
                END AS price_subtotal,
                rp.id AS partner_id,
                rp.vat AS vat,
                rp.city AS city_partner,
                rp.state_id AS state_id,
                am.invoice_user_id AS user_id,
                am.team_id AS team_id,
                so.state AS state_order,
                am.state AS state_invoice
            FROM
                sale_order so
                LEFT JOIN account_move am ON so.name = am.invoice_origin AND am.state = 'posted'
                LEFT JOIN res_partner rp ON so.partner_id = rp.id
                LEFT JOIN sale_order_line sol ON so.id = sol.order_id
                LEFT JOIN product_product pp ON sol.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN first_supplier fs ON pt.id = fs.product_tmpl_id AND fs.rn = 1
                LEFT JOIN product_category pc ON pt.categ_id = pc.id
                LEFT JOIN account_move_line aml ON am.id = aml.move_id
                AND aml.product_id = pp.id
            WHERE
                so.state IN ('sale', 'done', 'cancel')
                AND am.move_type IN ('out_invoice', 'out_refund')
                AND am.date BETWEEN %s AND %s
                AND so.company_id = %s
        """
        return self.prepare_query(query, start_date, end_date, partner_id, category_id, product_id, so=True)

    @api.model
    def prepare_query_pos_order(self, start_date, end_date, partner_id=None, category_id=None, product_id=None):
        query = """
            WITH first_supplier AS (
                SELECT
                    psi.product_tmpl_id,
                    psi.product_code,
                    psi.name,
                    ROW_NUMBER() OVER (PARTITION BY psi.product_tmpl_id ORDER BY psi.id) AS rn
                FROM
                    product_supplierinfo psi
            )
            SELECT
                pos.pos_reference AS pos_reference,
                pos.date_order AS date,
                pos.name AS order_name,
                am.name AS invoice_name,
                CASE
                    WHEN am.move_type = 'out_refund' THEN 'refund'
                    ELSE NULL
                END AS move_type,
                pp.default_code AS default_code,
                pp.id AS product_id,
                pt.id AS product_template_id,
                pt.detailed_type AS detailed_type,
                fs.product_code AS product_code,
                pc.id AS category_id,
                pt.product_brand_id AS product_brand_id,
                pt.uom_id AS uom_id,
                CASE
                    WHEN am.move_type = 'out_refund' THEN pol.qty * (-1)
                    ELSE pol.qty
                END AS quantity_invoiced,
                CASE
                    WHEN am.move_type = 'out_refund' THEN aml.price_subtotal * (-1)
                    ELSE aml.price_subtotal
                END AS price_subtotal,
                rp.id AS partner_id,
                rp.vat AS vat,
                rp.city AS city_partner,
                rp.state_id AS state_id,
                am.invoice_user_id AS user_id,
                am.team_id AS team_id
            FROM
                pos_order pos
                LEFT JOIN account_move am ON pos.account_move = am.id
                LEFT JOIN res_partner rp ON pos.partner_id = rp.id
                LEFT JOIN pos_order_line pol ON pos.id = pol.order_id
                LEFT JOIN product_product pp ON pol.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                LEFT JOIN first_supplier fs ON pt.id = fs.product_tmpl_id AND fs.rn = 1
                LEFT JOIN product_category pc ON pt.categ_id = pc.id
                LEFT JOIN account_move_line aml ON am.id = aml.move_id
                AND aml.product_id = pp.id
            WHERE
                pos.state = 'invoiced'
                AND am.move_type IN ('out_invoice', 'out_refund')
                AND am.date >= %s AND am.date <= %s
                AND pos.company_id = %s
        """
        return self.prepare_query(query, start_date, end_date, partner_id, category_id, product_id)

    @api.model
    def get_bom_details(self):
        self.env.cr.execute("""
            SELECT
                mb.product_tmpl_id,
                pt.name,
                mbl.product_qty
            FROM
                mrp_bom_line AS mbl
                JOIN mrp_bom AS mb ON mbl.bom_id = mb.id
                JOIN product_product AS pp ON mbl.product_id = pp.id
                JOIN product_template AS pt ON pp.product_tmpl_id = pt.id
        """)

        result = self.env.cr.fetchall()

        bom_dict = {}
        for record in result:
            product_tmpl_id, product_name, product_qty = record
            product_info = f"{product_name} : {product_qty}"
            bom_dict.setdefault(product_tmpl_id, []).append(product_info)

        return bom_dict

    @api.model
    def get_report_data(self, start_date, end_date, partner_id=None, category_id=None, product_id=None):
        if start_date > end_date:
            raise ValidationError(
                _("The start date must be before the end date."))

        query_sale, params_sale = self.prepare_query_sale_order(
            start_date, end_date, partner_id, category_id, product_id)
        query_pos, params_pos = self.prepare_query_pos_order(
            start_date, end_date, partner_id, category_id, product_id)

        self.env.cr.execute(query_sale, params_sale)
        results_sale = self.env.cr.dictfetchall()

        self.env.cr.execute(query_pos, params_pos)
        results_pos = self.env.cr.dictfetchall()

        results = results_sale + results_pos
        if not results:
            raise UserError(_("No data found. Try different criteria."))

        results.sort(key=lambda x: x['order_name'])
        return results

    @api.model
    def generate_report(self, start_date, end_date, partner_id=None, category_id=None, product_id=None):
        self.search([]).unlink()

        results = self.get_report_data(
            start_date, end_date, partner_id, category_id, product_id)
        bom_dict = self.get_bom_details()

        if isinstance(end_date, datetime.date):
            end_date = datetime.datetime.combine(end_date, datetime.time.max)

        for line in results:
            if isinstance(line['date'], datetime.date):
                line['date'] = datetime.datetime.combine(
                    line['date'], datetime.time.min)
            if line['date'] > end_date:
                continue
            product_tmpl_id = self.env['product.product'].browse(
                line['product_id']).product_tmpl_id.id
            bom_details = "\n".join(bom_dict.get(product_tmpl_id, []))
            line['product_detail'] = bom_details

            if 'pos_reference' not in line:
                line['pos_reference'] = None
            if 'state_order' not in line:
                line['state_order'] = None
            if 'state_invoice' not in line:
                line['state_invoice'] = None

            if not line['pos_reference']:
                if line['state_order'] == 'cancel' and line['state_invoice'] != 'posted':
                    continue

            self.create(line)

        return {
            'name': _('Sale Order Report'),
            'type': 'ir.actions.act_window',
            'view_mode': 'list,pivot',
            'res_model': 'sale.order.report',
            'target': 'current',
            'domain': [],
            'context': {},
        }
