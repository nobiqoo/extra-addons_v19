# -*- coding: utf-8 -*-

from cmath import pi
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    customer_dealer = fields.Selection([('customer', 'Customer'),
                                        ('dealer', 'Dealer')],
                                       'Customer type')
    o_country_id = fields.Many2one('res.country', 'Country')
    o_state_id = fields.Many2one('res.country.state', 'Department')
    o_city_id = fields.Many2one('res.city', 'Origin city')
    o_shipping_address = fields.Char('Shipping address')
    damage_type_id = fields.Many2one('damage.type.sm', 'Damage type')
    invoice_number = fields.Char('Invoice number')
    technician_id = fields.Many2one('res.partner', 'Technician')
    tech_city_id = fields.Many2one('res.city', 'City')
    retry_ticket_id = fields.Many2one('helpdesk.ticket', 'Re-entry ticket')
    image_sm_ids = fields.One2many('helpdesk.ticket.image.sm',
                                   'ticket_id',
                                   'Images')
    date_start_sm = fields.Datetime('Date init')
    date_due_sm = fields.Date('Date due')
    days_after_init = fields.Integer('Days after init',
                                     compute="_compute_days_after_init")
    days_after_init_str = fields.Char('Alert management days',
                                      compute="_compute_days_after_init")
    guide_number = fields.Char('Guía de salida')
    url_guide = fields.Char('URL guía de salida', compute='_compute_url_guide')
    guide_number_in = fields.Char('Guía de entrada')
    url_guide_in = fields.Char(
        'URL guía de entrada', compute='_compute_url_guide')
    date_in_ctb = fields.Date('CTB entry date')
    date_out_ctb = fields.Date('CTB departure date')
    # warehouse_product_id = fields.Many2one(
    #     'stock.warehouse',
    #     'Warehouse',
    #     domain="[('company_id', '=', company_id)]",
    #     help='Warehouse for product reception'
    # )
    location_product_id = fields.Many2one(
        'stock.location',
        'Location',
        help='Location for product reception'
    )
    product_picking_ids = fields.One2many(
        'stock.picking',
        'product_ticket_id',
        string='Product inventory orders',
        copy=False
    )
    stock_product_input_count = fields.Integer(
        'Product entries count',
        compute='_compute_stock_product'
    )
    stock_product_output_count = fields.Integer(
        'Product outputs count',
        compute='_compute_stock_product'
    )
    stock_product_picking_count = fields.Integer(
        'Product orders count',
        compute='_compute_stock_product'
    )
    partner_vat = fields.Char('Identificación')
    partner_mobile = fields.Char('Celular')
    product_categ_id = fields.Many2one(
        'product.category', 'Categoría de producto')
    product_brand_id = fields.Many2one('product.brand', 'Fabricante')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('partner_id'):
                partner_obj = self.env['res.partner']
                partner_id = partner_obj.browse(vals.get('partner_id'))
                vals['partner_vat'] = partner_id and partner_id.vat or ''
                vals['partner_mobile'] = partner_id and partner_id.mobile or ''
            if vals.get('product_id'):
                product_obj = self.env['product.product']
                product_id = product_obj.browse(vals.get('product_id'))
                vals['product_categ_id'] = product_id and product_id.categ_id and product_id.categ_id.id or False
                vals['product_brand_id'] = product_id and product_id.product_brand_id and product_id.product_brand_id.id or False
            if vals.get('technician_id') and self.env.user.has_group('helpdesk_extended.group_helpdesk_sales_sm'):
                raise ValidationError(
                    _("No esta autorizado para seleccionar el técnico encargado de la revisión del caso"))
        res = super().create(vals_list)
            # for record in res:
            #     partner_id = record.partner_id or False
            #     record.partner_vat = partner_id and partner_id.vat or '',
            #     record.partner_mobile = partner_id and partner_id.mobile or ''
        return res

    # @api.model
    # def write(self, vals):
    #    res = super(HelpdeskTicket, self).write(vals)
    #    user = self.env.user
    #    if not user.has_group('	helpdesk.group_helpdesk_manager'):
    #        raise ValidationError(_("No esta autorizado para editar el ticket, contacte a soporte si cree que deberia tener el permiso"))
    #    res = super(HelpdeskTicket, self).write(vals)
    #    return res

    @api.onchange('partner_id')
    def _onchange_partner_vat_mobile(self):
        partner_id = self.partner_id or False
        return {
            'value': {
                'partner_vat': partner_id and partner_id.vat or '',
                'partner_mobile': partner_id and partner_id.mobile or ''
            }
        }

    @api.onchange('product_id')
    def _onchange_product_category_brand(self):
        product_id = self.product_id or False
        return {
            'value': {
                'product_categ_id': product_id
                and product_id.categ_id
                and product_id.categ_id.id or False,
                'product_brand_id': product_id
                and product_id.product_brand_id
                and product_id.product_brand_id.id or False
            }
        }

    # @api.onchange('stage_id')
    # def _onchange_stage(self):
    #    if not self.stage_id.is_restricted:
    #        warning = ''
    #        if not self.env.user.has_group('helpdesk_extended.group_helpdesk_sales_sm'):
    #            warning += 'Lo sentimos, usted no esta autorizado para realizar cambios en esta Etapa.\n\n'
    #        if warning:
    #            raise ValidationError(warning)

    def _compute_stock_product(self):
        for record in self:
            record.stock_product_input_count = len(
                record.product_picking_ids.filtered(
                    lambda p: p.picking_type_code == 'incoming'
                )
            )
            record.stock_product_output_count = len(
                record.product_picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing'
                )
            )
            record.stock_product_picking_count = len(
                record.product_picking_ids.filtered(
                    lambda p: p.state != 'cancel'
                )
            )

    @api.depends('guide_number', 'guide_number_in')
    def _compute_url_guide(self):
        for record in self:
            url = 'https://mobile.servientrega.com/' \
                'WebSitePortal/RastreoEnvioDetalle.html?Guia=%s'
            if record.guide_number:
                record.url_guide = url % record.guide_number or ''
            else:
                record.url_guide = False
            if record.guide_number_in:
                record.url_guide_in = url % record.guide_number_in or ''
            else:
                record.url_guide_in = False

    def _compute_days_after_init(self):
        for record in self:
            if record.date_start_sm:
                date_init = fields.Datetime.from_string(record.date_start_sm)
                date_now = fields.Datetime.now()
                date_diff = \
                    record.team_id.resource_calendar_id.get_work_duration_data(
                        date_init, date_now
                    )
                days = int(date_diff.get('days'))
            else:
                days = 0

            record.days_after_init = days
            record.days_after_init_str = '%s %s' % (
                days,
                days == 1 and _('day') or _('days')
            )

    def action_open_product_picking(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Product Orders'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.product_picking_ids.ids)],
            'context': dict(
                self._context,
                create=False,
                default_company_id=self.company_id.id
            )
        }
        if len(self.product_picking_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.product_picking_ids.id
            })
        return action

    def action_open_product_output(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Output Orders'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.product_picking_ids.ids)],
            'context': dict(
                self._context,
                create=False,
                default_company_id=self.company_id.id
            )
        }
        if len(self.product_picking_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.product_picking_ids.id
            })
        return action

    def _prepare_product_picking_in(self):
        self.ensure_one()
        if not self.product_id:
            raise ValidationError(_(
                'There is not a product to enter.'
            ))
        if not self.location_product_id:
            raise ValidationError(_(
                'There is not a location to enter the product.'
            ))
        warehouse_id = self.env['stock.warehouse'].search(
            [('lot_stock_id', '=', self.location_product_id.id)]
        )
        picking_type_id = warehouse_id.in_type_id
        picking_val = {
            'picking_type_id': picking_type_id.id,
            'partner_id': self.partner_id.id,
            # 'user_id': self.env.user.id, TODO
            'date': fields.Date.today(),
            'origin': 'Ticket #%s' % self.id,
            # 'location_dest_id': picking_type_id.default_location_dest_id.id,
            'location_id': self.partner_id.property_stock_customer.id,
            'company_id': self.company_id.id,
            'owner_id': self.partner_id.id,
            'product_ticket_id': self.id,
            # 'move_ids': []
        }
        picking_line = {
            'name': (self.product_id.display_name or '')[:2000],
            'product_id': self.product_id.id,
            # 'date': fields.Date.today(),
            # 'date_deadline': False,  # TODO
            # 'location_dest_id': picking_type_id.default_location_dest_id.id,
            # 'location_id': self.partner_id.property_stock_customer.id,
            # 'picking_id': picking_id.id,
            # 'partner_id': False,  # TODO
            # 'move_dest_ids': False,  # TODO
            # 'state': 'draft',
            # 'company_id': self.company_id.id,
            # 'price_unit': False,  # TODO
            # 'picking_type_id': picking_type_id.id,  # TODO
            # 'group_id': False,  # TODO
            # 'origin': 'Ticket #%s' % self.id,
            # 'description_picking': (self.product_id.display_name or '')[:2000],
            # 'propagate_cancel': False,  # TODO
            # 'warehouse_id': warehouse_id.id,
            'product_uom_qty': 1,
            'product_uom': self.product_id.uom_id.id,
            # 'product_packaging_id': False,  # TODO
        }
        picking_val['move_ids'] = [(0, 0, picking_line)]
        return picking_val, picking_line

    def _prepare_product_picking_out(self):
        self.ensure_one()
        if not self.product_id:
            raise ValidationError(_(
                'There is not a product to deliver.'
            ))
        if not self.location_product_id:
            raise ValidationError(_(
                'There is not a location to remove the product.'
            ))
        warehouse_id = self.env['stock.warehouse'].search(
            [('lot_stock_id', '=', self.location_product_id.id)]
        )
        picking_type_id = warehouse_id.out_type_id
        picking_val = {
            'picking_type_id': picking_type_id.id,
            'partner_id': self.partner_id.id,
            # 'user_id': self.env.user.id, TODO
            'date': fields.Date.today(),
            'origin': 'Ticket #%s' % self.id,
            'location_dest_id': self.partner_id.property_stock_customer.id,
            # 'location_id': picking_type_id.default_location_src_id.id,
            'company_id': self.company_id.id,
            'owner_id': self.partner_id.id,
            'product_ticket_id': self.id,
            # 'move_ids': []
        }
        picking_line = {
            'name': (self.product_id.display_name or '')[:2000],
            'product_id': self.product_id.id,
            # 'date': fields.Date.today(),
            # 'date_deadline': False,  # TODO
            # 'location_dest_id': self.partner_id.property_stock_customer.id,
            # 'location_id': picking_type_id.default_location_src_id.id,
            # 'picking_id': picking_id.id,
            # 'partner_id': False,  # TODO
            # 'move_dest_ids': False,  # TODO
            # 'state': 'draft',
            # 'company_id': self.company_id.id,
            # 'price_unit': False,  # TODO
            # 'picking_type_id': picking_type_id.id,  # TODO
            # 'group_id': False,  # TODO
            # 'origin': 'Ticket #%s' % self.id,
            # 'description_picking': (self.product_id.display_name or '')[:2000],
            # 'propagate_cancel': False,  # TODO
            # 'warehouse_id': warehouse_id.id,
            'product_uom_qty': 1,
            'product_uom': self.product_id.uom_id.id,
            # 'product_packaging_id': False,  # TODO
        }
        picking_val['move_ids'] = [(0, 0, picking_line)]
        return picking_val, picking_line

    def register_product_entry(self):
        self.ensure_one()
        picking_in_id = self.product_picking_ids.filtered(
            lambda p: p.picking_type_code == 'incoming' and
            p.state != 'cancel'
        )
        if not picking_in_id:
            pick_vals, pick_line_vals = self._prepare_product_picking_in()

            pick_vals = {
                'default_%s' % k: v
                for k, v in pick_vals.items()
            }
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Input Orders'),
                'res_model': 'stock.picking',
                'view_mode': 'form',
                # 'res_id': picking_in_id.id,
                # 'domain': [('id', 'in', self.product_picking_ids.ids)],
                'context': dict(
                    self._context,
                    **pick_vals
                )
            }
        else:
            action = self.action_open_product_input()
        return action

    def register_product_output(self):
        self.ensure_one()
        picking_out_id = self.product_picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and
            p.state != 'cancel'
        )
        if not picking_out_id:
            pick_vals, pick_line_vals = self._prepare_product_picking_out()

            pick_vals = {
                'default_%s' % k: v
                for k, v in pick_vals.items()
            }
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Input Orders'),
                'res_model': 'stock.picking',
                'view_mode': 'form',
                # 'res_id': picking_out_id.id,
                # 'domain': [('id', 'in', self.product_picking_ids.ids)],
                'context': dict(
                    self._context,
                    **pick_vals
                )
            }
        else:
            action = self.action_open_product_input()

        return action
