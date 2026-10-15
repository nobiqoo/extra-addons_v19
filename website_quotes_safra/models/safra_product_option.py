# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SafraProductOption(models.Model):
    """Opciones configurables de la parametrización de productos.

    La matriz pide que U_Categoria, U_GrupoProd, U_ModoCorte, Prefijo y
    U_color sean listas desplegables con un menú donde el cliente cree sus
    propias opciones (filas F141/F163/F166/F167/F171).
    """
    _name = 'safra.product.option'
    _description = 'Opción de Parametrización de Producto'
    _order = 'type, sequence, name'

    # U_color NO va aquí: apunta a los productos marcados "Es color del
    # cotizador" (safra_is_color), que ya son la lista unificada de colores.
    OPTION_TYPES = [
        ('categoria', 'U_Categoria (segmento de ventas)'),
        ('grupo_prod', 'U_GrupoProd (tipo de artículo)'),
        ('modo_corte', 'U_ModoCorte'),
        ('prefijo', 'Prefijo (ItemCode)'),
        ('ref_categoria', 'Categoría de referencia (Tela, Sesgo…)'),
    ]

    name = fields.Char(string='Opción', required=True)
    type = fields.Selection(OPTION_TYPES, string='Tipo', required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    # Reunión 13-oct (filas 56-57): en las referencias de esta categoría
    # cada línea dice para qué motores sirve y cuántos canales tiene (un
    # mismo control del maestro puede ir como monocanal y como multicanal).
    es_control = fields.Boolean(
        string='Controles de motor',
        help='Categoría de referencia para controles: sus líneas muestran '
             'las columnas Motores y Canales.')
    # Solo para prefijos: consecutivo del ItemCode (F172: "cálculo automático
    # del prefijo y el número siguiente").
    next_number = fields.Integer(
        string='Próximo número', default=1,
        help='Consecutivo que tomará el próximo ItemCode generado con este prefijo.')
    padding = fields.Integer(
        string='Dígitos', default=5,
        help='Cantidad de dígitos del consecutivo (relleno con ceros).')

    @api.model
    def next_item_code(self, option):
        """Genera el siguiente ItemCode para un prefijo y avanza el consecutivo."""
        option.ensure_one()
        code = '%s%s' % (option.name, str(option.next_number).zfill(option.padding or 5))
        option.next_number += 1
        return code
