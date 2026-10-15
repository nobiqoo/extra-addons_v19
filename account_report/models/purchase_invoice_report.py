from odoo import fields, models, tools, api

class PurchaseInvoiceReport(models.Model):
    _name = 'purchase.invoice.report'
    _description = 'Report detailing purchases by weight'
    _auto = False

    partner_identification = fields.Char('Partner Identification')
    partner_name = fields.Char('Partner Name')
    invoice = fields.Char('Invoice')
    invoice_origin = fields.Char('Invoice Origin') 
    invoice_date = fields.Date('Invoice Date')
    invoice_expiration_date = fields.Date('Invoice Expiration Date')  
    product_category = fields.Char('Product Category')
    product_reference = fields.Char('Product Reference')
    product = fields.Char('Product')
    product_weight = fields.Float('Product Weight')
    product_quantity = fields.Float('Product Quantity')
    total_weight = fields.Float('Total Weight')
    product_uom = fields.Char('Unit of Measure')
    price_unit = fields.Float('Price Unit')
    price_subtotal = fields.Float('Price Subtotal')

    product_lang = fields.Char('Product', compute='_get_product_info')
    product_uom_lang = fields.Char('Unit of Measure', compute='_get_product_uom_info')

    @api.depends('product')
    def _get_product_info(self):
        lang = self.env.user.lang 
        for rec in self:
            rec.product_lang = rec.product.get(lang if lang in rec.product else list(rec.product.keys())[0], '')
    
    @api.depends('product_uom')
    def _get_product_uom_info(self):
        lang = self.env.user.lang  
        for rec in self:
            rec.product_uom_lang = rec.product_uom.get(lang, list(rec.product_uom.values())[0]) if isinstance(rec.product_uom, dict) else rec.product_uom or ''
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW purchase_invoice_report AS (
                SELECT 
                    row_number() over () AS id,
                    RP.vat AS partner_identification, 
                    RP.name AS partner_name, 
                    AM.name AS invoice, 
                    AM.invoice_origin AS invoice_origin,  
                    AM.invoice_date AS invoice_date, 
                    AM.invoice_date_due AS invoice_expiration_date,  
                    PC.name AS product_category, 
                    PT.default_code AS product_reference, 
                    PT.name AS product, 
                    PP.weight AS product_weight, 
                    CASE WHEN AM.move_type = 'in_refund' THEN -AML.quantity ELSE AML.quantity END AS product_quantity,
                    PP.weight * AML.quantity AS total_weight, 
                    UOM.name AS product_uom, 
                    AML.price_unit AS price_unit, 
                    CASE WHEN AM.move_type = 'in_refund' THEN -AML.price_subtotal ELSE AML.price_subtotal END AS price_subtotal
                FROM account_move AS AM
                INNER JOIN res_partner AS RP
                    ON RP.id = AM.partner_id
                INNER JOIN account_move_line AS AML
                    ON AML.move_id = AM.id
                INNER JOIN product_product AS PP
                    ON PP.id = AML.product_id
                INNER JOIN product_template AS PT
                    ON PT.id = PP.product_tmpl_id
                INNER JOIN product_category AS PC
                    ON PC.id = PT.categ_id
                INNER JOIN uom_uom AS UOM
                    ON UOM.id = AML.product_uom_id
                WHERE 
                    AM.move_type IN ('in_invoice', 'in_refund') AND
                    AM.state = 'posted' AND AML.display_type = 'product'
            )
        ''')
