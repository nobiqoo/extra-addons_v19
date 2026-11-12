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
        # Reunión 15-oct (fila 68): los tubos de la Estructura por Ancho, para
        # marcar en el maestro a qué tubo pertenece cada insumo.
        ('tubo', 'Tubo (Estructura por Ancho)'),
        # Sprint 1.6 (fila 132): unidad de negocio para los informes.
        ('unidad_negocio', 'Unidad de negocio (informes)'),
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
    # Sprint 1.5 (fila 99): en las referencias de rieles cada línea dice
    # cuántos canales (vías) tiene y si es el Riel Velcrado; con eso se
    # cruza el Tipo de Riel con la combinación de telos (E20029).
    es_riel = fields.Boolean(
        string='Rieles',
        help='Categoría de referencia para rieles de panel: sus líneas '
             'muestran las columnas Canales y Velcrado.')
    # Sprint 1.2 (pendiente de la reunión 13-oct, comentario del 15-oct):
    # las asociaciones del motor (módulo RF y cargador) viven en las líneas
    # de la referencia de motores, no en el maestro.
    es_motor = fields.Boolean(
        string='Motores',
        help='Categoría de referencia para motores: sus líneas muestran las '
             'columnas Requiere módulo RF, Ítem módulo RF, Requiere cargador '
             'e Ítem cargador.')
    # Solo para prefijos: consecutivo del ItemCode (F172: "cálculo automático
    # del prefijo y el número siguiente").
    next_number = fields.Integer(
        string='Próximo número', default=1,
        help='Consecutivo que tomará el próximo ItemCode generado con este prefijo.')
    padding = fields.Integer(
        string='Dígitos', default=5,
        help='Cantidad de dígitos del consecutivo (relleno con ceros).')

    @api.model
    def _setup_embalaje(self):
        """Ajustes Sprint 1.6 (26-oct, fila 127): categoría de referencias
        «Embalaje»; sus líneas (con el producto del maestro) son las
        opciones del Embalaje del pedido. Reusa una existente."""
        Option = self.sudo().with_context(active_test=False)
        cat = Option.search([('type', '=', 'ref_categoria'), ('name', '=ilike', 'embalaje')], limit=1)
        if not cat:
            cat = Option.create({'type': 'ref_categoria', 'name': 'Embalaje', 'sequence': 100})
        self.env['ir.model.data'].sudo()._update_xmlids([{
            'xml_id': 'website_quotes_safra.popt_refcat_embalaje', 'record': cat, 'noupdate': True}])
        return True

    @api.model
    def _categoria_embalaje(self):
        return self.env.ref('website_quotes_safra.popt_refcat_embalaje', raise_if_not_found=False) \
            or self.browse()

    @api.model
    def next_item_code(self, option):
        """Genera el siguiente ItemCode para un prefijo y avanza el consecutivo."""
        option.ensure_one()
        # Sprint 1.6 (fila 162): el ItemCode es único; si el consecutivo ya
        # lo usa otro producto (p. ej. uno cargado desde SAP), se salta.
        Product = self.env['product.template'].sudo().with_context(active_test=False)
        while True:
            code = '%s%s' % (option.name, str(option.next_number).zfill(option.padding or 5))
            option.next_number += 1
            if not Product.search_count([('safra_item_code', '=', code)]):
                return code
