# -*- coding: utf-8 -*-

from functools import lru_cache
from odoo import api, fields, models, _

selection_due = [
    ('000', '0'),
    ('030', '1 - 30'),
    ('060', '31 - 60'),
    ('090', '61 - 90'),
    ('120', '91 - 120'),
    ('190', '121 - 180'),
    ('360', '191 - 360'),
    ('inf', 'Mayor'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_term_due = fields.Selection(
        selection=selection_due,
        compute='_compute_invoice_term_due',
        store=True,
    )
    date_aux = fields.Date(
        related='date',
        string="account date auxiliar"
    )
    # TODO
    current_exchange_rate = fields.Float(
        string='Current exchange rate',
        compute='_compute_current_exchange_rate',
        inverse='_inverse_current_exchange_rate',
        store=True, readonly=False,
        digits=(16, 4)
    )
    hide_credit_note_button = fields.Boolean(
        compute='_compute_hide_credit_note_button',
    )

    @api.depends('company_id.hide_credit_note_fully_credited', 'amount_total',
                 'reversal_move_ids.state', 'reversal_move_ids.amount_total')
    def _compute_hide_credit_note_button(self):
        """Política de la compañía: sin botón Nota de crédito si las notas publicadas ya cubren el total."""
        for move in self:
            hide = False
            if move.company_id.hide_credit_note_fully_credited and move.move_type in ('out_invoice', 'in_invoice'):
                credited = sum(move.reversal_move_ids.filtered(lambda r: r.state == 'posted').mapped('amount_total'))
                hide = move.currency_id.compare_amounts(credited, move.amount_total) >= 0
            move.hide_credit_note_button = hide

    @api.depends('invoice_currency_rate')
    def _compute_current_exchange_rate(self):
        for move in self:
            move.current_exchange_rate = 1 / (move.invoice_currency_rate or 1)

    @api.onchange('current_exchange_rate')
    def _inverse_current_exchange_rate(self):
        for move in self:
            move.invoice_currency_rate = 1 / (move.current_exchange_rate or 1)

    @api.depends('state', 'payment_state', 'invoice_date_due')
    def _compute_invoice_term_due(self):

        def _get_term_selection():
            selection = []
            for term in selection_due[:-1]:
                selection.append(int(term[0]))
            return selection

        def _get_term_pair():
            terms_list = []
            terms = _get_term_selection()
            for i in range(len(terms)):
                terms_list.append(tuple(terms[i:i+2]))
            return terms_list

        def _get_term_days(days):
            term_pair = _get_term_pair()
            for term in term_pair:
                low = term[0]
                high = len(term) > 1 and term[1] or float('inf')
                if days > low and days <= high:
                    return str(high)
            return str('0')

        invoices = self.filtered(lambda i: i.is_invoice())
        moves = invoices.filtered(
            lambda m: m.state == 'posted' and m.payment_state in (
                'not_paid',
                'partial'
            )
        )
        for move in moves:
            today = fields.Date.today()
            date = move.invoice_date_due
            days = (today - date).days
            invoice_term_due = str(_get_term_days(days)).zfill(3)
            move.update({'invoice_term_due': invoice_term_due})
        (self - invoices).update({'invoice_term_due': False})
        (invoices - moves).update({'invoice_term_due': '000'})

    def _reverse_moves(self, default_values_list=None, cancel=False):
        reverse_moves = super(AccountMove, self)._reverse_moves(
            default_values_list, cancel)

        if reverse_moves:
            for reverse_move in reverse_moves:
                if reverse_move.move_type == 'out_refund':
                    # Solo las líneas de producto: las de costo de venta conservan sus cuentas
                    for line in reverse_move.line_ids.filtered(lambda l: l.display_type == 'product' and l.product_id):
                        account = line._get_refund_account()
                        if account:
                            line.update({'account_id': account.id})
        return reverse_moves

    def _can_write_partner_invoice(self):
        self.ensure_one()
        return ((self.company_id.manage_partner_in_invoice_lines_out and self.move_type == 'out_invoice')
                or (self.company_id.manage_partner_in_invoice_lines_in and self.move_type == 'in_invoice'))

    def _get_manual_line_partners(self):
        """Contacto y cuenta de los apuntes de las facturas en borrador cuya política permite editar el contacto por línea."""
        return {
            move: {line: (line.partner_id, line.account_id) for line in move.line_ids}
            for move in self
            if move.state == 'draft' and move._can_write_partner_invoice()
        }

    def _restore_manual_line_partners(self, manual_values):
        """El core fuerza en _post el contacto de la cabecera en todos los apuntes; aquí se devuelve el editado manualmente."""
        for values in manual_values.values():
            for line, (partner, account) in values.items():
                if not line.exists():
                    continue
                vals = {}
                if line.partner_id != partner:
                    vals['partner_id'] = partner.id
                if line.account_id != account:
                    vals['account_id'] = account.id
                if vals:
                    line.write(vals)

    def _post(self, soft=True):
        manual_values = self._get_manual_line_partners()
        posted = super()._post(soft=soft)
        self._restore_manual_line_partners(manual_values)
        return posted

    def _stock_account_prepare_realtime_out_lines_vals(self):
        """Obsequios/promociones: gasto configurable y analítica opcional en el débito COGS.

        En Odoo 19 el core vuelve a usar _stock_account_prepare_realtime_out_lines_vals
        (en 18 era _stock_account_prepare_anglo_saxon_out_lines_vals).
        En 19 ambas líneas COGS traen analytic_distribution, así que la línea de
        inventario se distingue por la cuenta de valoración del producto.
        """
        lines_vals_list = super()._stock_account_prepare_realtime_out_lines_vals()
        InvoiceLine = self.env['account.move.line']
        for vals in lines_vals_list:
            if vals.get('display_type') != 'cogs':
                continue
            origin_id = vals.get('cogs_origin_id')
            if not origin_id:
                continue
            origin = InvoiceLine.browse(origin_id)
            if not origin.exists() or not origin._is_promotion_gift_line():
                continue
            move = self.browse(vals['move_id'])
            accounts = origin.product_id.product_tmpl_id.with_company(move.company_id).get_product_accounts(
                fiscal_pos=move.fiscal_position_id)
            if vals.get('account_id') == accounts['stock_valuation'].id:
                continue
            company = move.company_id
            if company.account_sale_stock_out_expense_id:
                vals['account_id'] = company.account_sale_stock_out_expense_id.id
            dist = company.promotion_gift_cogs_analytic_distribution
            if dist is not False and dist is not None:
                vals['analytic_distribution'] = dist if dist else {}
        return lines_vals_list
