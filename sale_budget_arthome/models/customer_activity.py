from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


PARAM_INACTIVITY_MONTHS = 'sale_budget_arthome.customer_inactivity_months'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_last_sale_date = fields.Date(
        string='Fecha de última venta', readonly=True, copy=False, index=True,
        help='Fecha del pedido confirmado más reciente del cliente.',
    )
    x_customer_activity_status = fields.Selection(
        [('active', 'Activo'), ('inactive', 'Inactivo')],
        string='Estado del cliente', readonly=True, copy=False, index=True,
        default='inactive', required=True,
    )

    @api.model
    def _customer_inactivity_months(self):
        value = self.env['ir.config_parameter'].sudo().get_param(PARAM_INACTIVITY_MONTHS, '6')
        try:
            return max(int(value), 1)
        except (TypeError, ValueError):
            return 6

    def _refresh_customer_activity(self):
        partners = self.sudo().exists()
        if not partners:
            return
        grouped = self.env['sale.order'].sudo()._read_group(
            [('partner_id', 'in', partners.ids), ('state', 'in', ['sale', 'done'])],
            ['partner_id'], ['date_order:max'],
        )
        last_order_dates = {partner.id: date_order for partner, date_order in grouped}
        cutoff = fields.Date.context_today(self) - relativedelta(months=self._customer_inactivity_months())
        for partner in partners:
            last_datetime = last_order_dates.get(partner.id)
            last_date = False
            if last_datetime:
                timezone = partner.tz or partner.company_id.partner_id.tz or self.env.user.tz
                last_date = fields.Datetime.context_timestamp(
                    partner.with_context(tz=timezone), last_datetime,
                ).date()
            status = 'active' if last_date and last_date >= cutoff else 'inactive'
            values = {}
            if partner.x_last_sale_date != last_date:
                values['x_last_sale_date'] = last_date
            if partner.x_customer_activity_status != status:
                values['x_customer_activity_status'] = status
            if values:
                partner.with_context(skip_customer_activity_refresh=True).write(values)

    @api.model
    def _cron_update_customer_activity(self):
        order_partners = self.env['sale.order'].sudo()._read_group(
            [('state', 'in', ['sale', 'done'])], ['partner_id'], [],
        )
        partner_ids = [partner.id for (partner,) in order_partners]
        partners = self.sudo().with_context(active_test=False).search([
            '|', ('customer_rank', '>', 0), ('id', 'in', partner_ids),
        ])
        partners._refresh_customer_activity()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_last_sale_date = fields.Date(
        related='partner_id.x_last_sale_date', string='Fecha de última venta',
        store=True, readonly=True,
    )
    x_customer_activity_status = fields.Selection(
        related='partner_id.x_customer_activity_status', string='Estado del cliente',
        store=True, readonly=True,
    )

    def _customer_activity_partners(self):
        return self.mapped('partner_id')

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders.filtered(lambda order: order.state in ('sale', 'done'))._customer_activity_partners()._refresh_customer_activity()
        return orders

    def write(self, vals):
        relevant = {'partner_id', 'state', 'date_order'}
        partners = self._customer_activity_partners() if relevant.intersection(vals) else self.env['res.partner']
        result = super().write(vals)
        if relevant.intersection(vals):
            (partners | self._customer_activity_partners())._refresh_customer_activity()
        return result

    def unlink(self):
        partners = self.filtered(lambda order: order.state in ('sale', 'done'))._customer_activity_partners()
        result = super().unlink()
        partners._refresh_customer_activity()
        return result


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    customer_inactivity_months = fields.Integer(
        string='Meses sin ventas para considerar un cliente inactivo',
        config_parameter=PARAM_INACTIVITY_MONTHS,
        default=6,
        required=True,
    )

    @api.constrains('customer_inactivity_months')
    def _check_customer_inactivity_months(self):
        for settings in self:
            if settings.customer_inactivity_months < 1:
                raise ValidationError(_('El periodo de inactividad debe ser de al menos un mes.'))

    def set_values(self):
        result = super().set_values()
        self.env['res.partner']._cron_update_customer_activity()
        return result
