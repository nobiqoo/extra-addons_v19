# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMoveLine(models.Model):
    """Línea de factura con el ReteICA de la sede (tarea 10340).

    La inyección se engancha al cálculo estándar de impuestos en lugar de
    hacerse con un onchange sobre la factura. Así se cubren de una sola vez los
    tres comportamientos pedidos:

    - al elegir la sede se recalculan todas las líneas (``operation_site_id``
      se agrega a las dependencias de ``_compute_tax_ids``; el ORM fusiona los
      ``@api.depends`` de los overrides recorriendo la MRO);
    - las líneas que se agreguen después nacen ya con el impuesto, porque pasan
      por el mismo cálculo;
    - el ReteICA se suma a lo que devuelva Webkul/Odoo para el producto, de
      modo que el IVA y los demás impuestos se conservan.

    Al cambiar la sede, el impuesto de la anterior desaparece solo: el cálculo
    parte de los impuestos del producto y vuelve a agregar el de la sede
    vigente.
    """

    _inherit = 'account.move.line'

    @api.depends('move_id.operation_site_id')
    def _compute_tax_ids(self):
        return super()._compute_tax_ids()

    def _get_computed_taxes(self):
        taxes = super()._get_computed_taxes()
        site = self.move_id.operation_site_id
        if not site or self.display_type != 'product':
            return taxes
        reteica = site._get_reteica_tax(self.move_id.move_type)
        if not reteica:
            return taxes
        # El ReteICA se agrega a los impuestos del producto, nunca los sustituye.
        return (taxes or self.env['account.tax']) | reteica
