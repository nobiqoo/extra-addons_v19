# -*- coding: utf-8 -*-

from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    fiscal_position_local = fields.Boolean('Posición Fiscal Local',
                                            compute='_compute_fiscal_position_local')

    dian_brand = fields.Char('Marca',
                    help='Marca reportada en la '
                    'factura electrónica a la DIAN.')
    dian_model = fields.Char('Modelo',
                    help='Modelo reportado en la '
                    'factura electrónica a la DIAN.')
    dian_customs_code = fields.Char('Código Aduanero',
                    help='Necesario principalmente '
                    'para facturas de exportación.')
    dian_unspsc_id = fields.Many2one('product.unspsc.dian_code',
                    'Categoría UNSPSC',
                    domain=[('applies_to', '=', 'product')],
                    help='El código UNSPSC relacionado con este producto. '
                    'Utilizado para edi en Colombia, Perú y México')
    third_party_income = fields.Boolean('Ingreso de Terceros',
                    help='Indica si el producto es un ingreso de terceros, '
                    'para reportar en la factura electrónica a la DIAN. (Mandatos)',
                    default=False)
    dian_nominal_tax = fields.Float(
                    string='Componente Específico para Impuestos Nominales', 
                    help='Para impuesto IBUA: Volumen en mililitros.\nPara impuesto ICL: % de alcohol en la bebida.',
                    compute='_compute_dian_nominal_tax',
                    inverse='_set_dian_nominal_tax')
    
    def _compute_fiscal_position_local(self):
        for record in self:
            if record.company_id:
                record.fiscal_position_local = record.company_id.fiscal_position_local
            else:
                record.fiscal_position_local = self.env.company.fiscal_position_local
    
    @api.depends('product_variant_ids.dian_nominal_tax')
    def _compute_dian_nominal_tax(self):
        self._compute_template_field_from_variant_field('dian_nominal_tax')

    def _set_dian_nominal_tax(self):
        self._set_product_variant_field('dian_nominal_tax')

class ProductProduct(models.Model):
    _inherit = 'product.product'

    dian_nominal_tax = fields.Float(
                    string='Componente Específico para Impuestos Nominales', 
                    help='Para impuesto IBUA: Volumen en mililitros.\nPara impuesto ICL: % de alcohol en la bebida.')
