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
                if reverse_move.move_type in ('out_invoice', 'out_refund'):
                    for line in reverse_move.line_ids:
                        account = line.product_id.product_tmpl_id.categ_id.property_account_refund_categ_id
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

