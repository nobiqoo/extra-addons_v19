# -*- coding: utf-8 -*-
import copy

from odoo import api, models

PURCHASE_TYPES = "('in_invoice', 'in_refund', 'in_receipt')"


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            self._set_optional_account_on_purchase_lines(arch)
        return arch, view

    @api.model
    def _set_optional_account_on_purchase_lines(self, arch):
        """ En documentos de proveedor la columna Cuenta de las líneas de
        factura queda oculta por defecto y disponible en columnas opcionales.
        Como la vista es la misma para cliente y proveedor, se duplica la
        columna: la copia (opcional) solo se muestra en proveedor y la
        original solo en cliente. Se hace sobre la vista ya combinada para
        conservar los cambios que otros módulos hagan a la columna.
        """
        for field in arch.xpath("//field[@name='invoice_line_ids']/list/field[@name='account_id']"):
            if field.get('optional') or field.get('column_invisible') in ('1', 'True', 'true'):
                continue
            current = field.get('column_invisible')
            purchase_field = copy.deepcopy(field)
            purchase_field.set('optional', 'hide')
            purchase_field.set('column_invisible', self._or_condition(current, f"parent.move_type not in {PURCHASE_TYPES}"))
            field.set('column_invisible', self._or_condition(current, f"parent.move_type in {PURCHASE_TYPES}"))
            field.addnext(purchase_field)

    @api.model
    def _or_condition(self, current, condition):
        return f"({current}) or {condition}" if current else condition
