# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools import SQL

from odoo.addons.sale.models.sale_order import SALE_ORDER_STATE


class SaleShippingReport(models.Model):
    _name = 'sale.shipping.report'
    _description = "Sales Shipping Information"
    _auto = False
    _rec_name = 'name'
    _order = 'date_order desc, id desc'

    order_id = fields.Many2one(comodel_name='sale.order', string="Sales Order", readonly=True)
    name = fields.Char(string="Order Reference", readonly=True)
    date_order = fields.Datetime(string="Order Date", readonly=True)
    state = fields.Selection(selection=SALE_ORDER_STATE, string="Status", readonly=True)
    user_id = fields.Many2one(comodel_name='res.users', string="Salesperson", readonly=True)
    team_id = fields.Many2one(comodel_name='crm.team', string="Sales Team", readonly=True)
    company_id = fields.Many2one(comodel_name='res.company', string="Company", readonly=True)
    currency_id = fields.Many2one(comodel_name='res.currency', string="Currency", readonly=True)
    partner_id = fields.Many2one(comodel_name='res.partner', string="Customer", readonly=True)
    partner_name = fields.Char(string="Customer Name", readonly=True)
    shipping_city = fields.Char(string="Shipping City", readonly=True)
    shipping_state = fields.Char(string="Shipping State", readonly=True)
    shipping_street = fields.Char(string="Shipping Address", readonly=True)
    phone = fields.Char(string="Phone", readonly=True)
    email = fields.Char(string="Email", readonly=True)
    invoice_names = fields.Char(string="Invoice Number", readonly=True)
    insurable_value = fields.Monetary(string="Insurable Value", currency_field='currency_id', readonly=True)
    carrier_partner_id = fields.Many2one(comodel_name='res.partner', string="Carrier", readonly=True)
    carrier_tracking_number = fields.Char(string="Tracking Number", readonly=True)

    @property
    def _table_query(self):
        return self._query()

    def _query(self):
        return SQL(
            """
            WITH picking_steps AS (
                -- Paso de cada transferencia del pedido: salida (3), empaque (2) o recolección (1)
                SELECT picking.sale_id,
                       picking.insurable_value,
                       CASE
                           WHEN picking_type.code = 'outgoing' THEN 3
                           WHEN picking_type.id = warehouse.pack_type_id THEN 2
                           WHEN picking_type.id = warehouse.pick_type_id THEN 1
                       END AS step
                  FROM stock_picking picking
                  JOIN stock_picking_type picking_type ON picking_type.id = picking.picking_type_id
             LEFT JOIN stock_warehouse warehouse ON warehouse.id = picking_type.warehouse_id
                 WHERE picking.sale_id IS NOT NULL
                   AND picking.state != 'cancel'
            ),
            insurable AS (
                -- Solo suma el paso más avanzado para no repetir el valor de PICK, PACK y OUT
                SELECT sale_id, SUM(insurable_value) AS insurable_value
                  FROM (
                      SELECT sale_id, insurable_value, step, MAX(step) OVER (PARTITION BY sale_id) AS last_step
                        FROM picking_steps
                       WHERE step IS NOT NULL
                  ) steps
                 WHERE step = last_step
              GROUP BY sale_id
            ),
            invoices AS (
                SELECT line.order_id,
                       STRING_AGG(DISTINCT move.name, ', ' ORDER BY move.name) AS invoice_names
                  FROM sale_order_line line
                  JOIN sale_order_line_invoice_rel rel ON rel.order_line_id = line.id
                  JOIN account_move_line move_line ON move_line.id = rel.invoice_line_id
                  JOIN account_move move ON move.id = move_line.move_id
                 WHERE move.move_type = 'out_invoice'
                   AND move.state = 'posted'
              GROUP BY line.order_id
            )
            SELECT so.id,
                   so.id AS order_id,
                   so.name,
                   so.date_order,
                   so.state,
                   so.user_id,
                   so.team_id,
                   so.company_id,
                   so.currency_id,
                   commercial.id AS partner_id,
                   commercial.name AS partner_name,
                   -- La dirección de envío manda; si un dato está vacío se toma el del cliente del pedido
                   COALESCE(
                       ship_city.name->>%(lang)s, ship_city.name->>'en_US', NULLIF(shipping.city, ''),
                       partner_city.name->>%(lang)s, partner_city.name->>'en_US', NULLIF(partner.city, '')
                   ) AS shipping_city,
                   COALESCE(ship_state.name, partner_state.name) AS shipping_state,
                   COALESCE(
                       NULLIF(CONCAT_WS(' ', NULLIF(shipping.street, ''), NULLIF(shipping.street2, '')), ''),
                       NULLIF(CONCAT_WS(' ', NULLIF(partner.street, ''), NULLIF(partner.street2, '')), '')
                   ) AS shipping_street,
                   commercial.phone,
                   commercial.email,
                   invoices.invoice_names,
                   COALESCE(insurable.insurable_value, 0) AS insurable_value,
                   so.carrier_partner_id,
                   so.carrier_tracking_number
              FROM sale_order so
              JOIN res_partner partner ON partner.id = so.partner_id
              JOIN res_partner commercial ON commercial.id = partner.commercial_partner_id
              JOIN res_partner shipping ON shipping.id = COALESCE(so.partner_shipping_id, so.partner_id)
         LEFT JOIN res_city ship_city ON ship_city.id = shipping.city_id
         LEFT JOIN res_country_state ship_state ON ship_state.id = shipping.state_id
         LEFT JOIN res_city partner_city ON partner_city.id = partner.city_id
         LEFT JOIN res_country_state partner_state ON partner_state.id = partner.state_id
         LEFT JOIN insurable ON insurable.sale_id = so.id
         LEFT JOIN invoices ON invoices.order_id = so.id
            """,
            lang=self.env.lang or 'en_US',
        )

    @api.readonly
    def action_open_order(self):
        """Abre el pedido de venta de la fila."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'views': [[False, 'form']],
            'res_id': self.order_id.id,
        }
