# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductProduct(models.Model):
    """Marca los productos que son Libro, para poder filtrar el campo
    "Libro" de la Clase ofertada/Inscripción.

    Ronda de ajustes post-prueba: mismo patrón ya usado en el módulo base
    para "Elementos de tarifa" -un Boolean simple como domain, en vez de un
    catálogo o categoría nueva- (`is_fee_element`/`libray_element`,
    `wk_school_management/models/fee_structure.py:16-21`). Sin este check,
    el selector de Libro traería todos los productos (certificados,
    exámenes, cuotas, etc.) sin forma de distinguir cuáles son libros.
    """

    _inherit = 'product.product'

    is_book_element = fields.Boolean(string="¿Es libro?", default=False)

    is_benefit_discount_element = fields.Boolean(
        string="¿Es concepto de descuento/beneficio?", default=False,
        help="Producto usado para representar, como línea independiente del "
             "recibo de tarifa, el valor de un beneficio/cupón aplicado "
             "(tarea 11856, 2.13). Mismo patrón que is_book_element/"
             "is_fee_element: un Boolean simple como domain en vez de un "
             "catálogo nuevo.")


class ProductTemplate(models.Model):
    """Espejo de is_benefit_discount_element hacia el Producto (template):
    la mayoría de productos de este colegio no tiene variantes, y el usuario
    gestiona el catálogo desde Ventas > Productos (product.template), no
    desde Variantes de producto (product.product) -mismo patrón genérico que
    ya usa el core para barcode/weight/standard_price
    (_compute_template_field_from_variant_field/_set_product_variant_field,
    addons/product/models/product_template.py)-. Con más de una variante (o
    ninguna) el campo del template queda en False y hay que marcarlo en la
    variante directamente.
    """

    _inherit = 'product.template'

    is_book_element = fields.Boolean(
        string="¿Es libro?",
        compute='_compute_is_book_element',
        inverse='_set_is_book_element', store=False)

    is_benefit_discount_element = fields.Boolean(
        string="¿Es concepto de descuento/beneficio?",
        compute='_compute_is_benefit_discount_element',
        inverse='_set_is_benefit_discount_element', store=False)

    @api.depends('product_variant_ids.is_book_element')
    def _compute_is_book_element(self):
        self._compute_template_field_from_variant_field('is_book_element')

    def _set_is_book_element(self):
        self._set_product_variant_field('is_book_element')

    @api.depends('product_variant_ids.is_benefit_discount_element')
    def _compute_is_benefit_discount_element(self):
        self._compute_template_field_from_variant_field(
            'is_benefit_discount_element')

    def _set_is_benefit_discount_element(self):
        self._set_product_variant_field('is_benefit_discount_element')
