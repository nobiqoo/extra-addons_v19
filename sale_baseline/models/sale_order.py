# -*- coding: utf-8 -*-

from dateutil import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import formatLang
from datetime import datetime, timedelta


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_edit_salesperson = fields.Boolean(
        string='Salesperson editable',
        compute='_compute_is_editable_salesperson'
    )

    show_confirm_button = fields.Boolean(
        string='Show confirm button',
        compute='_show_confirm_button'
    )
    unlock_for_credit_limit = fields.Boolean(
        'Autorizar con LdC',
        help='Autorizar si el cliente esta bloqueado por límite de crédito.',
        default=False
    )
    unlock_for_overdue_invoices = fields.Boolean(
        'Autorizar con Fac. Ven.',
        help='Autorizar si el cliente esta bloqueado por facturas vencidas.',
        default=False
    )
    check_user_edit_line = fields.Boolean(
        compute="compute_check_user_edit_line"
    )

    @api.depends('company_id', 'company_id.salesperson_not_editable')
    def _compute_is_editable_salesperson(self):
        for record in self:
            editable = False
            if record.company_id.salesperson_not_editable:
                user_id = self.env.user
                if user_id.has_group('sale_baseline.group_edit_salesperson'):
                    editable = True
            else:
                editable = True
            record.is_edit_salesperson = editable

    def _add_tag_to_non_buyers(self):
        company_ids = self.env['res.company'].search([])
        for company_id in company_ids.filtered(lambda x: x.add_tag_to_non_buyers):
            self = self.with_company(company_id)
            partner_obj = self.env['res.partner']
            month_validate = company_id.months_without_buying
            tag_id = company_id.tags_to_add_ids
            date_now = fields.Date.today()
            partner_ids = partner_obj.search([('customer_rank', '>', 0)])
            all_partner_ids = partner_obj.search([])
            all_partner_ids = all_partner_ids.filtered(
                lambda p: tag_id in p.category_id and
                p.id not in partner_ids.ids)
            if all_partner_ids:
                all_partner_ids.with_company(company_id).write({
                    'category_id': [(3, tag_id.id, 0)],
                    'is_blocked_not_buy': False
                })
            for partner_id in partner_ids:
                sale_id = self._get_last_sale_confirmed(
                    partner_id.sale_order_ids)
                if sale_id:
                    date_order = sale_id.date_order
                    month_real = relativedelta.relativedelta(
                        date_now, date_order.date()).months
                    if month_real >= month_validate:
                        partner_id.with_company(company_id).write({
                            'category_id': [(4, tag_id.id, 0)],
                            'is_blocked_not_buy': True
                        })
                    elif tag_id in partner_id.category_id:
                        partner_id.with_company(company_id).write({
                            'category_id': [(3, tag_id.id, 0)],
                            'is_blocked_not_buy': False
                        })
                    else:
                        partner_id.with_company(company_id).write({
                            'is_blocked_not_buy': False
                        })
                else:
                    partner_id.with_company(company_id).write({
                        'category_id': [(4, tag_id.id, 0)],
                        'is_blocked_not_buy': True
                    })

    def _get_last_sale_confirmed(self, sale_ids):
        sales = sorted(
            sale_ids.filtered(lambda s: s.state == 'sale'),
            key=lambda s: s.date_order,
            reverse=True
        )
        if sales:
            return sales[0]
        else:
            return False

    def _get_invoices_due(self, now, invoices):
        list_due_invoices = []
        for record in invoices:
            days_due = (now - record.invoice_date_due).days
            if days_due >= record.company_id.day_limit_invoice_block:
                list_due_invoices.append(record.id)
        return self.env['account.move'].browse(list_due_invoices)

    def action_confirm(self):
        self = self.with_context(mto_by_demand=True)
        for record in self:
            now = datetime.now() - timedelta(hours=5)
            now = now.date()
            if record.company_id.add_tag_to_non_buyers \
                and record.partner_id.is_blocked_not_buy \
                    and not self.env.user.has_group(
                        'sale_baseline.group_confirm_partner_locked_no_buy'):
                raise ValidationError(_(
                    'Customer blocked for time without making purchases.'))
            if record.company_id.block_expired_invoice \
                and record.partner_id.block_expired_invoice \
                    and not record.unlock_for_overdue_invoices:
                invoices = self.env['account.move'].search(
                    [('partner_id', '=', record.partner_id.id),
                     ('invoice_date_due', '<=', now),
                     ('state', '=', 'posted'),
                     ('payment_state', '!=', 'paid'),
                     ('move_type', '=', 'out_invoice')]
                )
                invoices = record._get_invoices_due(now, invoices)
                if len(invoices) > 0:
                    raise ValidationError(
                        _('El cliente tiene las siguientes facturas vencidas: \n'
                          '%s',
                          '\n'.join(['* %s (%s)' % (x.name, x.invoice_date_due) for x in invoices])))

            if record.company_id.block_credit_limit \
                and record.partner_id.block_credit_limit \
                    and record.payment_term_id.immediate_payment == False \
                and not record.unlock_for_credit_limit:
                partner_id = record.partner_id
                # Get the partner that holds the credit limit (parent if shared)
                credit_limit_partner = partner_id._get_credit_limit_partner()

                # Calculate total shared credit (from all partners sharing the limit)
                total_shared_credit = credit_limit_partner._get_total_shared_credit()

                # Add current order amount
                updated_credit = total_shared_credit + \
                    (record.amount_total / record.currency_rate)

                # Get orders without invoice for all shared partners
                orders_no_invoice_amount = credit_limit_partner._get_shared_orders_no_invoice_amount(
                    record.currency_rate)
                updated_credit += orders_no_invoice_amount

                if updated_credit > credit_limit_partner.credit_limit:
                    # Prepare message based on whether credit is shared
                    if credit_limit_partner != partner_id:
                        error_msg = _(
                            '%(pr)s ha superado el Límite de crédito compartido de %(parent)s: %(lc)s\n\n'
                            'Crédito Utilizado: %(cr)s\n'
                            'Valor orden: %(vt)s',
                            pr=partner_id.name,
                            parent=credit_limit_partner.name,
                            lc=formatLang(
                                self.env, credit_limit_partner.credit_limit, currency_obj=record.company_id.currency_id),
                            cr=formatLang(self.env, total_shared_credit +
                                          orders_no_invoice_amount, currency_obj=record.company_id.currency_id),
                            vt=formatLang(self.env, record.amount_total / record.currency_rate, currency_obj=record.company_id.currency_id))
                    else:
                        error_msg = _(
                            '%(pr)s ha superado su Límite de crédito: %(lc)s\n\n'
                            'Crédito: %(cr)s\n'
                            'Valor orden: %(vt)s',
                            pr=partner_id.name,
                            lc=formatLang(
                                self.env, credit_limit_partner.credit_limit, currency_obj=record.company_id.currency_id),
                            cr=formatLang(self.env, total_shared_credit +
                                          orders_no_invoice_amount, currency_obj=record.company_id.currency_id),
                            vt=formatLang(self.env, record.amount_total / record.currency_rate, currency_obj=record.company_id.currency_id))
                    raise ValidationError(error_msg)

            if record.company_id.active_payment_advance \
                and not record.advance_payment_manually \
                    and record.payment_term_id.immediate_payment:
                if not record.account_voucher_ids:
                    raise ValidationError(
                        _("Una cuenta anticipo mínimo debe estar relacionada con el pedido."))
                else:
                    accounts_noval = []
                    accounts_name = ''
                    for account in record.account_voucher_ids:
                        if account.state != 'posted':
                            accounts_name += account.name + " \n"
                            accounts_noval.append(account)

                    if accounts_noval:
                        raise ValidationError(
                            _("Las cuentas: \n %s \n no están publicadas.",
                                accounts_name))

                    sum_account_advance = sum(
                        [x.amount for x in record.account_voucher_ids])
                    if record.amount_total > sum_account_advance:
                        raise ValidationError(
                            _("Los anticipos acumulados no superan el total del pedido."))

            scq = self.env.company.sale_confirm_quantity
            if not scq:
                return super(SaleOrder, self).action_confirm()
            for line in record.order_line:
                if not line.product_id:
                    continue
                if line.product_id.type not in ('product', 'consu'):
                    continue
                product_uom_qty = line.product_uom_qty
                product_uom = line.product_uom
                product = line.product_id.with_context(
                    warehouse=record.warehouse_id.id)
                uom_id = line.product_id.uom_id

                free_qty = product.free_qty

                quantity = product_uom._compute_quantity(
                    product_uom_qty, uom_id)

                if (free_qty < quantity) and scq:
                    raise ValidationError(_(
                        'The order cannot be confirmed.\n Only %s of %s of the product %s is available.'
                    ) % (free_qty, quantity, line.product_id.display_name))

        return super(SaleOrder, self).action_confirm()

    @api.depends('company_id', 'company_id.allow_confirm_sale_for_administrators')
    def _show_confirm_button(self):
        for record in self:
            has_group_sale_manager = self.env.user.has_group(
                'sales_team.group_sale_manager')
            allow_confirm_sale_for_administrators = self.env.company.allow_confirm_sale_for_administrators
            record.show_confirm_button = has_group_sale_manager or not allow_confirm_sale_for_administrators

    @api.depends('partner_id', 'order_line')
    def compute_check_user_edit_line(self):
        for record in self:
            company = record.company_id
            if company.restriction_line_price:
                edit_line = False
                if self.env.user.has_group(
                        'sale_baseline.group_line_price_edit'):
                    edit_line = True
                record.check_user_edit_line = edit_line
                for line in record.order_line:
                    line.check_user_edit_line = edit_line
            else:
                record.check_user_edit_line = True
                for line in record.order_line:
                    line.check_user_edit_line = True
