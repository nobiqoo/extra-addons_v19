# -*- coding: utf-8 -*-
import re

from odoo import models
from odoo.tools import format_date

NO_CATEGORY_LABEL = 'Otros'
# Dígitos con los que se compara el valor unitario al agrupar. price_unit no
# se redondea en la línea, así que 0,329 y 0,33 deben quedar en grupos aparte.
PRICE_GROUP_DIGITS = 6

WEBFLOR_GENERAL_FIELDS = [
    ('webflor_order_number', 'Pedido WebFlor'),
    ('webflor_invoice_number', 'Invoice WebFlor'),
    ('webflor_sale_type', 'Tipo de venta'),
    ('webflor_negotiation_term', 'Término de negociación'),
    ('webflor_order_type', 'Tipo de orden'),
]
WEBFLOR_LOGISTIC_FIELDS = [
    ('webflor_freight_forwarder', 'Agencia de carga'),
    ('webflor_airline', 'Aerolínea'),
    ('webflor_delivery_date', 'Fecha de entrega'),
    ('webflor_dispatch_date', 'Fecha de despacho'),
    ('webflor_mawb_number', 'Guía madre (MAWB)'),
    ('webflor_hawb_number', 'Guía hija (HAWB)'),
    ('webflor_grandchild_guide_number', 'Guía nieta'),
]

# Textos fijos de la representación gráfica en inglés. Las etiquetas de la
# plantilla de l10n_co_bloodo están escritas en español como texto fuente, así
# que el mecanismo de traducción de Odoo no puede pasarlas a inglés.
RG_TEXTS_EN = {
    # Encabezado
    'NIT: ': 'Tax ID: ',
    'Tel: ': 'Phone: ',
    'Factura Electrónica de Venta N°: ': 'Electronic Sales Invoice No.: ',
    'Factura de Venta N°: ': 'Sales Invoice No.: ',
    'Nota Crédito Electrónica N°: ': 'Electronic Credit Note No.: ',
    'Nota Crédito de Venta N°: ': 'Sales Credit Note No.: ',
    'Nota Débito Electrónica N°: ': 'Electronic Debit Note No.: ',
    'Nota Débito de Venta N°: ': 'Sales Debit Note No.: ',
    # Datos del cliente
    'DATOS DEL CLIENTE': 'CUSTOMER INFORMATION',
    'FECHA VALIDACIÓN': 'VALIDATION DATE',
    'FECHA FACTURA': 'INVOICE DATE',
    'FECHA VENCIMIENTO': 'DUE DATE',
    'Razón Social:': 'Company Name:',
    'NIT:': 'Tax ID:',
    'Dirección:': 'Address:',
    'Ciudad:': 'City:',
    'Teléfono:': 'Phone:',
    'Celular:': 'Mobile:',
    'Dirección de entrega:': 'Delivery Address:',
    'Ubicación:': 'Location:',
    'Plazo de pago:': 'Payment Terms:',
    'Medio de pago:': 'Payment Method:',
    'Vendedor:': 'Salesperson:',
    'Orden de pedido:': 'Purchase Order:',
    'Moneda:': 'Currency:',
    'TRM:': 'Exchange Rate (TRM):',
    'Incoterm:': 'Incoterm:',
    # Notas crédito / débito
    'Factura Afectada:': 'Referenced Invoice:',
    'CONCEPTO DE CORRECCION': 'CORRECTION REASON',
    'Fecha Factura:': 'Invoice Date:',
    # Detalle
    'ITEM': 'ITEM',
    'REF.': 'REF.',
    'DESCRIPCIÓN': 'DESCRIPTION',
    'CANTIDAD': 'QUANTITY',
    'UNIDAD': 'UNIT',
    'V. UNITARIO': 'UNIT PRICE',
    'DTO. (%)': 'DISC. (%)',
    'SUBTOTAL': 'SUBTOTAL',
    'CATEGORÍA: ': 'CATEGORY: ',
    'Subtotal ': 'Subtotal ',
    NO_CATEGORY_LABEL: 'Others',
    # WebFlor
    'INFORMACIÓN WEBFLOR': 'WEBFLOR INFORMATION',
    'LOGÍSTICA / ADUANA': 'LOGISTICS / CUSTOMS',
    'Pedido WebFlor': 'WebFlor Order',
    'Invoice WebFlor': 'WebFlor Invoice',
    'Tipo de venta': 'Sale Type',
    'Término de negociación': 'Negotiation Term',
    'Tipo de orden': 'Order Type',
    'Agencia de carga': 'Freight Forwarder',
    'Aerolínea': 'Airline',
    'Fecha de entrega': 'Delivery Date',
    'Fecha de despacho': 'Dispatch Date',
    'Guía madre (MAWB)': 'Master Air Waybill (MAWB)',
    'Guía hija (HAWB)': 'House Air Waybill (HAWB)',
    'Guía nieta': 'Sub-house Air Waybill',
    # Cuotas
    'PLAN DE PAGOS': 'PAYMENT SCHEDULE',
    'CUOTA': 'INSTALLMENT',
    'VENCIMIENTO': 'DUE DATE',
    'VALOR': 'AMOUNT',
    # Totales y pie
    'Tipo de moneda': 'Currency',
    'Pesos ($)': 'Colombian Pesos (COP)',
    'Subtotal': 'Subtotal',
    'Total': 'Total',
    'TOTAL EN LETRAS: ': 'TOTAL IN WORDS: ',
    'CUFE Factura:': 'Invoice CUFE:',
    'Por favor utilice la siguiente referencia al realizar su pago: ':
        'Please use the following reference when making your payment: ',
    'Fabricante Software y Proveedor Tecnológico: ODONE S.A.S.':
        'Software Manufacturer and Technology Provider: ODONE S.A.S.',
    'NIT: 901.361.603-8': 'Tax ID: 901.361.603-8',
    'Nombre Software: ODONE': 'Software Name: ODONE',
}

# Reemplazos que l10n_co_bloodo aplica al total en letras en español, con
# límite de palabra para no convertir "Centavos" en "Centavoavos".
RG_AMOUNT_WORDS_ES = [
    (r'\bDollars\b', 'Dolares'),
    (r'\bDollar\b', 'Dolar'),
    (r'\bCents\b', 'Centavos'),
    (r'\bCent\b', 'Centavo'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # Idioma
    # ------------------------------------------------------------------

    def _rg_is_english(self):
        """La RG de ventas se imprime en el idioma del cliente: español si su
        idioma es español, inglés en cualquier otro caso. Los documentos de
        compra (documento soporte) siempre en español."""
        self.ensure_one()
        if not self.is_sale_document(include_receipts=True):
            return False
        lang = self.partner_id.lang or self.partner_id.commercial_partner_id.lang
        if not lang:
            return False
        return not lang.startswith('es')

    def _get_rg_lang(self):
        """Código de idioma con el que se renderizan los campos traducibles."""
        self.ensure_one()
        if self._rg_is_english():
            return 'en_US'
        lang = self.partner_id.lang or self.partner_id.commercial_partner_id.lang
        if lang and lang.startswith('es') and self.env['res.lang']._lang_get(lang):
            return lang
        return self.env.lang

    def _rg_text(self, text):
        """Texto fijo de la RG en el idioma del cliente."""
        self.ensure_one()
        if self._rg_is_english():
            return RG_TEXTS_EN.get(text, text)
        return text

    def _rg_field_text(self, record, field_name):
        """Valor de un campo con versión en inglés (<campo>_en): si el cliente
        es de habla inglesa y el campo en inglés tiene contenido, se usa ese."""
        self.ensure_one()
        if self._rg_is_english() and record[field_name + '_en']:
            return record[field_name + '_en']
        return record[field_name]

    def _get_rg_amount_in_words(self):
        self.ensure_one()
        currency = self.currency_id
        if not currency:
            return ''
        if self._rg_is_english():
            return currency.with_context(lang='en_US').amount_to_text(self.amount_total).upper()
        text = currency.with_context(lang=self._get_rg_lang()).amount_to_text(self.amount_total)
        if currency.name == 'COP' and int(self.amount_total) != 1:
            text = re.sub(r'\bPeso\b', 'Pesos', text)
        if currency.name in ('USD', 'EUR'):
            for pattern, repl in RG_AMOUNT_WORDS_ES:
                text = re.sub(pattern, repl, text)
        return text.upper()

    # ------------------------------------------------------------------
    # Encabezado y cuotas
    # ------------------------------------------------------------------

    def _get_rg_delivery_rows(self):
        """Filas de dirección de entrega para los datos del cliente."""
        self.ensure_one()
        shipping = self.partner_shipping_id
        if not shipping:
            return []
        street = ', '.join(s for s in (shipping.street, shipping.street2) if s)
        city = shipping.city_id.name if 'city_id' in shipping._fields and shipping.city_id else shipping.city
        location = ' / '.join(s for s in (city, shipping.state_id.name, shipping.country_id.name) if s)
        return [
            (self._rg_text('Dirección de entrega:'), street),
            (self._rg_text('Ubicación:'), location),
        ]

    def _get_rg_installments(self):
        """Cuotas del término de pago (vencimientos de la factura). Solo hay
        tabla cuando el término genera más de un vencimiento."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.display_type == 'payment_term').sorted(
            lambda l: (l.date_maturity or l.date, l.id))
        if len(lines) < 2:
            return []
        return [{
            'number': index,
            'date_maturity': line.date_maturity,
            'amount': abs(line.amount_currency),
        } for index, line in enumerate(lines, start=1)]

    # ------------------------------------------------------------------
    # Detalle agrupado y WebFlor
    # ------------------------------------------------------------------

    def _get_rg_grouped_lines(self):
        """Agrupa las líneas de producto para la representación gráfica:
        nivel 1 por categoría (nombre en factura) y nivel 2 por valor unitario,
        unidad de medida y descuento. Los subtotales son la suma de los
        subtotales de las líneas, así cuadran con los totales certificados."""
        self.ensure_one()
        categories = {}
        for line in self.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product'):
            categ = line.product_id.categ_id
            label = (categ.invoice_label or categ.name) if categ else self._rg_text(NO_CATEGORY_LABEL)
            price = round(line.price_unit, PRICE_GROUP_DIGITS)
            key = (price, line.product_uom_id.id, line.discount)
            category = categories.setdefault(label, {'name': label, 'groups': {}})
            group = category['groups'].setdefault(key, {
                'description': label,
                'price_unit': price,
                'uom': line.product_uom_id.name or '',
                'discount': line.discount,
                'quantity': 0.0,
                'subtotal': 0.0,
            })
            group['quantity'] += line.quantity
            group['subtotal'] += line.price_subtotal

        no_category = self._rg_text(NO_CATEGORY_LABEL)
        result = []
        for label in sorted(categories, key=lambda n: (n == no_category, n.lower())):
            groups = sorted(categories[label]['groups'].values(),
                            key=lambda g: (g['price_unit'], g['uom'], g['discount']))
            uoms = {g['uom'] for g in groups}
            result.append({
                'name': label,
                'groups': groups,
                'quantity': sum(g['quantity'] for g in groups) if len(uoms) == 1 else False,
                'subtotal': sum(g['subtotal'] for g in groups),
            })
        return result

    def _get_rg_webflor_data(self):
        """Datos WebFlor de los pedidos de venta que originaron la factura.
        Con varios pedidos se concatenan los valores distintos."""
        self.ensure_one()
        orders = self.invoice_line_ids.sale_line_ids.order_id.sorted('name')

        def collect(field_list):
            rows = []
            for field_name, label in field_list:
                values = []
                for order in orders:
                    value = order[field_name]
                    if not value:
                        continue
                    if hasattr(value, 'strftime'):
                        value = format_date(self.env, value)
                    if value not in values:
                        values.append(value)
                rows.append((self._rg_text(label), ', '.join(values)))
            return rows

        general = collect(WEBFLOR_GENERAL_FIELDS)
        logistic = collect(WEBFLOR_LOGISTIC_FIELDS)
        if not any(value for _label, value in general + logistic):
            return {}
        return {'general': general, 'logistic': logistic}
