# -*- coding: utf-8 -*-
"""Campos numéricos que distinguen «sin digitar» de «digitado en 0».

Odoo guarda un Float vacío como 0 y lo muestra como 0,00. Safra necesita
saber si el dato se digitó: aquí el vacío se conserva (NULL en la base,
False al leer y en pantalla una casilla en blanco) y el 0 digitado queda 0.
En Python el vacío vale False, que en una cuenta actúa como 0, así que los
cálculos existentes no cambian.

En el backoffice, static/src/js/backend/campo_vacio.js hace que la casilla
vacía no se convierta en 0 al guardar.
"""
from odoo import api, fields, models


def _vacio(value):
    return value is None or value is False or (isinstance(value, str) and not value.strip())


class FloatVacio(fields.Float):
    # Buscar «= False» trae solo los vacíos y «= 0» solo los ceros (en un
    # Float normal las dos búsquedas traen ambos).
    falsy_value = None
    # El cliente web sabe que este campo admite vacío.
    _description_safra_vacio = True

    def convert_to_column(self, value, record, values=None, validate=True):
        if _vacio(value):
            return None
        return super().convert_to_column(value, record, values, validate)

    def convert_to_cache(self, value, record, validate=True):
        if _vacio(value):
            return None
        return super().convert_to_cache(value, record, validate)

    def convert_to_record(self, value, record):
        return False if value is None else value

    def convert_to_read(self, value, record, use_display_name=True):
        return False if value is None else value

    def convert_to_export(self, value, record):
        return '' if _vacio(value) else value


class IntegerVacio(fields.Integer):
    """Lo mismo que FloatVacio para los enteros."""
    falsy_value = None
    _description_safra_vacio = True

    def convert_to_column(self, value, record, values=None, validate=True):
        if _vacio(value):
            return None
        return super().convert_to_column(value, record, values, validate)

    def convert_to_cache(self, value, record, validate=True):
        if _vacio(value):
            return None
        return super().convert_to_cache(value, record, validate)

    def convert_to_record(self, value, record):
        return False if value is None else value

    def convert_to_read(self, value, record, use_display_name=True):
        return False if value is None else super().convert_to_read(value, record, use_display_name)

    def convert_to_export(self, value, record):
        return '' if _vacio(value) else value


def admite_vacio(field):
    """True si el campo distingue «sin digitar» de 0."""
    return isinstance(field, (FloatVacio, IntegerVacio))


# Cómo se nombra el registro en el aviso «Falta digitar …».
_DE_MODELO = {
    'product.template': 'del producto',
    'product.product': 'del producto',
    'safra.fabric': 'de la referencia',
    'safra.fabric.color': 'de la línea de la referencia',
    'safra.system': 'del sistema',
    'safra.structure.rule': 'de la fila de la Estructura por Ancho',
    'safra.lamas.rule': 'de la regla de lamas',
    'safra.field.option': 'de la opción',
    'safra.system.field.option': 'de la opción',
}


def dato_sin_digitar(record, fname):
    """Texto del dato vacío para el aviso: «Peso tela (g/m²) de la
    referencia «Atenas»»."""
    field = record._fields[fname]
    return '%s %s «%s»' % (field.string, _DE_MODELO.get(record._name, 'de'), record.display_name)


def vacio_en(record, fname):
    """True si `record` tiene `fname` sin digitar (y el campo lo admite)."""
    field = record._fields.get(fname) if record else None
    return bool(field and admite_vacio(field) and record[:1][fname] is False)


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def _get_view_field_attributes(self):
        # Las vistas solo reciben estos atributos de cada campo: sin
        # «safra_vacio» el backoffice no sabría que el campo admite vacío.
        return super()._get_view_field_attributes() + ['safra_vacio']
