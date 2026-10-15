from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    city_id = fields.Many2one(
        'res.city',
        string='Ciudad',
        compute='_compute_city_id',
        store=True,
        readonly=False,
        precompute=True,
    )

    @api.depends('partner_id', 'partner_id.city', 'partner_id.city_id')
    def _compute_city_id(self):
        for order in self:
            if order.state not in ('draft', 'sent'):
                continue
            partner = order.partner_id
            order.city_id = partner._get_or_create_city() if partner else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res.pop('city_id', None)
        return res

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        vals['city_id'] = self.city_id.id
        return vals

    # --- Trazabilidad comercial con WebFlor ---
    webflor_order_number = fields.Char(
        string='N° Pedido WebFlor',
        copy=False,
        tracking=True,
        help='Número del pedido generado en la plataforma WebFlor. '
             'Permite mantener la trazabilidad entre ambas plataformas.',
    )
    webflor_invoice_number = fields.Char(
        string='N° Invoice WebFlor',
        copy=False,
        tracking=True,
        help='Número del Invoice generado por WebFlor asociado a esta Orden de Venta.',
    )
    webflor_sale_type = fields.Char(
        string='Tipo de Venta',
        tracking=True,
        help='Tipo de venta asociado a la orden, según definición del negocio. '
             'Se completa vía integración con WebFlor.',
    )
    webflor_negotiation_term = fields.Char(
        string='Término de Negociación',
        tracking=True,
        help='Condición comercial bajo la cual se realiza la venta '
             '(ej.: Venta Directa, Crédito). Se completa vía integración con WebFlor.',
    )
    webflor_order_type = fields.Char(
        string='Tipo de Orden',
        tracking=True,
        help='Clasificación de la orden de venta (ej.: Fija, Open Market). '
             'Se completa vía integración con WebFlor.',
    )

    # --- Logística internacional (pestaña "WebFlor") ---
    webflor_freight_forwarder = fields.Char(
        string='Agencia de Carga',
        help='Empresa encargada del transporte internacional de la mercancía.',
    )
    webflor_airline = fields.Char(
        string='Aerolínea',
        help='Aerolínea utilizada para el despacho de la mercancía.',
    )
    webflor_mawb_number = fields.Char(
        string='Número de Guía Madre (MAWB)',
        help='Número de la guía aérea madre (Master Air Waybill).',
    )
    webflor_hawb_number = fields.Char(
        string='Número de Guía Hija (HAWB)',
        help='Número correspondiente a la guía hija (House Air Waybill).',
    )
    webflor_grandchild_guide_number = fields.Char(
        string='Número de Guía Nieta',
        help='Número correspondiente a la guía nieta, cuando aplique.',
    )
    webflor_delivery_date = fields.Date(
        string='Fecha de Entrega WebFlor',
        help='Fecha programada o efectiva de entrega al cliente. '
             'Se nombra distinto al campo estándar "Fecha de Entrega" '
             '(grupo Entrega) para evitar dos campos con la misma etiqueta '
             'en el mismo formulario.',
    )
    webflor_dispatch_date = fields.Date(
        string='Fecha de Despacho WebFlor',
        help='Fecha en la que se realiza el despacho de la mercancía.',
    )
