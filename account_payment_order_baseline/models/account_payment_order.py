# -*- coding: utf-8 -*-

import logging
import base64
from datetime import datetime, timedelta

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError

from .account_move import (
    _ORDER_STATE_AUTH,
    _UNRECONCILE_AUTH,
    _reconcile_lock_enabled,
)

_logger = logging.getLogger('__name__')


class AccountPaymentOrder(models.Model):
    _inherit = 'account.payment.order'

    current_exchange_rate = fields.Float(
        string='Current exchange rate',
        readonly=False,
    )
    foreign_currency = fields.Boolean(
        string='Active foreign currency',
        compute='compute_active_foreign_currency',
        readonly=True,
        store=True
    )
    total_currency_amount = fields.Monetary(
        compute='_total_currency_amount',
        currency_field='company_currency_id',
        store=True,
        string='Total currency amount'
    )
    total_company_currency_exchange_rate = fields.Monetary(
        compute='_total_company_currency_exchange_rate',
        currency_field='company_currency_id',
        store=True,
        string='Total currency amount (company)'
    )
    payment_type_order = fields.Selection(
        selection=[
            ('payroll', 'Payroll'),
            ('suppliers', 'Suppliers'),
            ('transfer', 'Transfer'),
        ],
        string='Payment Type'
    )

    @api.constrains("date_scheduled")
    def check_date_scheduled(self):
        today = fields.Date.context_today(self)
        for order in self:
            if order.date_scheduled:
                if order.date_scheduled < today:
                    _logger.warning(
                        _(
                            "On payment order %(porder)s, the Payment Execution Date "
                            "is in the past (%(exedate)s).",
                            porder=order.name,
                            exedate=order.date_scheduled,
                        )
                    )

    @api.depends('payment_line_ids',
                 'payment_line_ids.amount_company_currency',
                 'state')
    def _total_currency_amount(self):
        for rec in self:
            rec.total_currency_amount = sum(
                rec.mapped('payment_line_ids.amount_currency') or [0.0]
            )

    @api.depends('payment_line_ids',
                 'payment_line_ids.amount_company_currency',
                 'state')
    def _total_company_currency_exchange_rate(self):
        for rec in self:
            rec.total_company_currency_exchange_rate = sum(
                rec.mapped('payment_line_ids.amount_currency') or [0.0]
            )*rec.current_exchange_rate

    def default_date_order(self):
        return (datetime.today() - timedelta(hours=5)).date()

    order_date = fields.Date(
        string='Date order',
        default=default_date_order
    )

    def eval_foreing_currency(self):
        currency_id = self.company_id.currency_id
        foreign_currency = False
        for line in self.payment_line_ids:
            if line.currency_id != currency_id:
                foreign_currency = line.currency_id
        return foreign_currency

    @api.depends('payment_line_ids')
    def compute_active_foreign_currency(self):
        foreign_currency = self.eval_foreing_currency()
        self.foreign_currency = True if foreign_currency else False

    @api.onchange('payment_line_ids', 'foreign_currency')
    def _onchange_payment_line_ids(self):
        foreign_currency = self.eval_foreing_currency()
        if foreign_currency and self.order_date:
            amount = self.company_id.currency_id._get_conversion_rate(
                foreign_currency,
                self.company_id.currency_id,
                self.company_id,
                self.order_date
            )
            self.current_exchange_rate = amount
        else:
            self.current_exchange_rate = 1

    @api.depends('move_ids')
    def _compute_move_count(self):
        rg_res = self.env['account.move'].read_group(
            [('payment_order_id', 'in', self.ids)],
            ['payment_order_id'],
            ['payment_order_id'],
        )
        mapped_data = {
            x['payment_order_id'][0]:
            x['payment_order_id_count'] for x in rg_res
        }
        for order in self:
            order.move_count = mapped_data.get(order.id, 0)
        exch_moves = self.returns_number_of_exch_moves()
        order.move_count += exch_moves

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                payment_mode_id = vals.get("payment_mode_id") or self.env.context.get(
                    "default_payment_mode_id"
                )
                if payment_mode_id:
                    company = self.env["account.payment.mode"].browse(
                        payment_mode_id
                    ).company_id
                else:
                    company = self.env.company
                if not _reconcile_lock_enabled(company):
                    continue
                if vals.get("state", "draft") != "draft":
                    raise UserError(_(
                        "A payment order must be created in draft state."
                    ))
        clean_context = {
            key: value for key, value in self.env.context.items()
            if key != "default_state"
        }
        return super(AccountPaymentOrder, self.with_context(clean_context)).create(vals_list)

    def write(self, vals):
        if (
            "state" in vals
            and not self.env.su
            and self.env.context.get("allow_order_state_write") is not _ORDER_STATE_AUTH
        ):
            if vals.get("payment_mode_id"):
                target_company = self.env["account.payment.mode"].browse(
                    vals["payment_mode_id"]
                ).company_id
            else:
                target_company = None
            protected = self.filtered(
                lambda order: _reconcile_lock_enabled(order.company_id)
                or _reconcile_lock_enabled(target_company)
            )
            if protected:
                raise UserError(_(
                    "The state of a payment order cannot be changed directly."
                ))
        return super().write(vals)

    def action_cancel(self):
        protected = self.filtered(
            lambda order: _reconcile_lock_enabled(order.company_id)
        )
        if protected and not (
            self.env.su or self.env.user.has_group(
                "account_payment_order_baseline.group_action_cancel_payment_order"
            )
        ):
            raise UserError(_(
                "You are not allowed to cancel payment orders."
            ))
        authorized = self.with_context(
            allow_locked_payment_draft=_UNRECONCILE_AUTH,
            allow_order_state_write=_ORDER_STATE_AUTH,
        )
        if authorized.payment_mode_id.combined_move_account_payment_order and authorized.move_ids:
            authorized.move_ids.button_draft()
            authorized.move_ids.button_cancel()
        return super(AccountPaymentOrder, authorized).action_cancel()

    def cancel2draft(self):
        if not self.env.su:
            protected = self.filtered(
                lambda order: _reconcile_lock_enabled(order.company_id)
            )
            if protected.filtered(lambda order: order.state != "cancel"):
                raise UserError(_(
                    "You can only reset to draft payment orders that are in "
                    "cancel state."
                ))
        return super(AccountPaymentOrder, self.with_context(
            allow_order_state_write=_ORDER_STATE_AUTH
        )).cancel2draft()

    def action_open_remove_partners_wizard(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(
                _(
                    "Solo puede retirar proveedores cuando la orden de pago "
                    "está en borrador."
                )
            )
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account_payment_order_baseline.action_account_payment_order_remove_partners_wizard"
        )
        action["context"] = dict(self.env.context, default_order_id=self.id)
        return action

    def draft2open(self):
        """
        ODONE: Overwite method for combined journal entries
        Called when you click on the 'Confirm' button
        Set the 'date' on payment line depending on the 'date_prefered'
        setting of the payment.order
        Re-generate the account payments.
        """
        if not self.env.su:
            protected = self.filtered(
                lambda order: _reconcile_lock_enabled(order.company_id)
            )
            if protected.filtered(lambda order: order.state != "draft"):
                raise UserError(_(
                    "You can only confirm payment orders that are in draft state."
                ))
        self = self.with_context(allow_order_state_write=_ORDER_STATE_AUTH)
        today = fields.Date.context_today(self)
        for order in self:
            if not order.journal_id:
                raise UserError(
                    _("Missing Bank Journal on payment order %s.") % order.name
                )
            if (
                order.payment_method_id.bank_account_required
                and not order.journal_id.bank_account_id
            ):
                raise UserError(
                    _("Missing bank account on bank journal '%s'.")
                    % order.journal_id.display_name
                )
            if not order.payment_line_ids:
                raise UserError(
                    _("There are no transactions on payment order %s.") % order.name
                )
            # Unreconcile, cancel and delete existing account payments
            if order.payment_mode_id.combined_move_account_payment_order and order.move_ids:
                order.move_ids.button_draft()
                order.move_ids.button_cancel()
                for move in order.move_ids.filtered(lambda m: m.state == 'cancel'):
                    move.line_ids.unlink()
            order.payment_ids.action_draft()
            order.payment_ids.action_cancel()
            order.payment_ids.unlink()
            # Prepare account payments from the payment lines
            payline_err_text = []
            group_paylines = {}  # key = hashcode
            for payline in order.payment_line_ids:
                try:
                    payline.draft2open_payment_line_check()
                except UserError as e:
                    payline_err_text.append(e.args[0])
                # Compute requested payment date
                if order.date_prefered == "due":
                    requested_date = payline.ml_maturity_date or payline.date or today
                elif order.date_prefered == "fixed":
                    requested_date = order.date_scheduled or today
                else:
                    requested_date = today
                # No payment date in the past
                requested_date = order.order_date
                # inbound: check option no_debit_before_maturity
                if (
                    order.payment_type == "inbound"
                    and order.payment_mode_id.no_debit_before_maturity
                    and payline.ml_maturity_date
                    and requested_date < payline.ml_maturity_date
                ):
                    payline_err_text.append(
                        _(
                            "The payment mode '%(pmode)s' has the option "
                            "'Disallow Debit Before Maturity Date'. The "
                            "payment line %(pline)s has a maturity date %(mdate)s "
                            "which is after the computed payment date %(pdate)s.",
                            pmode=order.payment_mode_id.name,
                            pline=payline.name,
                            mdate=payline.ml_maturity_date,
                            pdate=requested_date,
                        )
                    )
                payline.date = requested_date
                # Group options
                hashcode = (
                    payline.payment_line_hashcode()
                    if order.payment_mode_id.group_lines
                    else payline.id
                )
                if hashcode in group_paylines:
                    group_paylines[hashcode]["paylines"] += payline
                    group_paylines[hashcode]["total"] += payline.amount_currency
                else:
                    group_paylines[hashcode] = {
                        "paylines": payline,
                        "total": payline.amount_currency,
                    }
            # Raise errors that happened on the validation process
            if payline_err_text:
                raise UserError(
                    _("There's at least one validation error:\n")
                    + "\n".join(payline_err_text)
                )

            order.env.flush_all()

            # Create account payments
            payment_vals = []
            for paydict in list(group_paylines.values()):
                # Block if a bank payment line is <= 0
                if paydict["total"] <= 0:
                    raise UserError(
                        _(
                            "The amount for Partner '%(partner)s' is negative "
                            "or null (%(amount).2f) !",
                            partner=paydict["paylines"][0].partner_id.name,
                            amount=paydict["total"],
                        )
                    )
                payment_vals.append(
                    paydict["paylines"]._prepare_account_payment_vals())
            new_payments = self.env["account.payment"].create(payment_vals)
            if order.payment_mode_id.combined_move_account_payment_order:
                """ If the payment mode of the order has the option to combine accounting
                    flows, generate the (draft) journal entry of each new payment so their
                    lines can be merged into a single combined entry, instead of leaving one
                    entry per payment. The individual entries are kept in draft (never
                    posted) and are discarded later on, in generated2uploaded().
                """
                new_payments._generate_journal_entry()
                if order.move_ids:
                    debit_line_vals_list = []
                    total_credit = 0
                    total_currency_credit = 0
                    credit_line_vals = None

                    for move in order.move_ids:
                        for line in move.line_ids:
                            if line.debit > 0:
                                debit_line_vals_list.append((0, 0, {
                                    'account_id': line.account_id.id,
                                    'debit': line.debit,
                                    'credit': 0,
                                    'name': line.name,
                                    'partner_id': line.partner_id.id,
                                    'currency_id': line.currency_id.id,
                                    'amount_currency': line.amount_currency,
                                }))
                            else:
                                total_credit += line.credit
                                total_currency_credit += line.amount_currency
                                if not credit_line_vals:
                                    credit_line_vals = {
                                        'account_id': line.account_id.id,
                                        'debit': 0,
                                        'credit': 0,
                                        'name': line.name,
                                        'partner_id': line.partner_id.id,
                                        'currency_id': line.currency_id.id,
                                        'amount_currency': 0,
                                    }

                    if credit_line_vals:
                        credit_line_vals['credit'] = total_credit
                        credit_line_vals['amount_currency'] = total_currency_credit
                        debit_line_vals_list.append((0, 0, credit_line_vals))

                    if debit_line_vals_list:
                        combined_move_vals = {
                            'date': order.move_ids[0].date,
                            'ref': order.move_ids[0].ref,
                            'journal_id': order.move_ids[0].journal_id.id,
                            'company_id': order.move_ids[0].company_id.id,
                            'currency_id': order.move_ids[0].currency_id.id,
                            'partner_id': False,
                            'line_ids': debit_line_vals_list,
                        }
                        combined_move = self.env['account.move'].create(
                            combined_move_vals)
                        order.move_ids = [(6, 0, [combined_move.id])]
        self.write({"state": "open"})
        return True

    def open2generated(self):
        if not self.env.su:
            protected = self.filtered(
                lambda order: _reconcile_lock_enabled(order.company_id)
            )
            if protected.filtered(lambda order: order.state != "open"):
                raise UserError(_(
                    "You can only generate the payment file for payment "
                    "orders that are in open state."
                ))
        return super(AccountPaymentOrder, self.with_context(
            allow_order_state_write=_ORDER_STATE_AUTH
        )).open2generated()

    def generated2uploaded(self):
        if not self.env.su:
            protected = self.filtered(
                lambda order: _reconcile_lock_enabled(order.company_id)
            )
            # "uploaded" is only tolerated for the combined-move mode's
            # documented idempotent retry (see the re-run guard further
            # below); any other mode must come strictly from "generated"
            # (L3 — the wider tolerance let a non-combined order re-enter
            # this method after already being uploaded).
            invalid = protected.filtered(
                lambda order: order.state != "generated"
                and not (
                    order.state == "uploaded"
                    and order.payment_mode_id.combined_move_account_payment_order
                )
            )
            if invalid:
                raise UserError(_(
                    "You can only upload payment orders that are in "
                    "generated state."
                ))
        self = self.with_context(allow_order_state_write=_ORDER_STATE_AUTH)
        if self.payment_mode_id.combined_move_account_payment_order and self.move_ids:
            # Guard against re-running this on an order that was already
            # processed: nothing below ever marked the order as "uploaded",
            # so a second click on an already-completed order tried to
            # action_post() the already-posted combined move, which
            # l10n_co_bloodo._post() rejects because it is no longer draft.
            if self.move_ids.filtered(lambda m: m.state == "posted"):
                self.write(
                    {"state": "uploaded",
                        "date_uploaded": self.date_uploaded or fields.Date.context_today(self)}
                )
                return True

            self.move_ids.action_post()

            # Capture the individual draft entries before payments get
            # re-pointed to the combined move below, otherwise this search
            # would no longer find them.
            draft_moves = self.find_draft_moves_linked_to_payments()

            for payment in self.payment_ids:

                payment_lines = payment.payment_line_ids.move_line_id

                combined_move_lines = self.move_ids.line_ids.filtered(
                    lambda line: line.account_id == payment.destination_account_id and
                    line.partner_id == payment.partner_id and
                    not line.reconciled
                )

                (payment_lines + combined_move_lines).reconcile()

                # Re-point the payment to the surviving combined move before
                # its own individual draft entry is discarded below.
                # Otherwise the payment keeps a non-draft state without any
                # journal entry, and account.payment._check_move_id() blocks
                # it from ever being confirmed again.
                payment.move_id = self.move_ids

            for move in draft_moves:
                move.unlink()

            self.write(
                {"state": "uploaded",
                    "date_uploaded": fields.Date.context_today(self)}
            )

        else:
            self.payment_ids.action_post()
            # Perform the reconciliation of payments and source journal items
            for payment in self.payment_ids:
                (
                    payment.payment_line_ids.move_line_id
                    + payment.move_id.line_ids.filtered(
                        lambda x, p=payment: x.account_id == p.destination_account_id
                    )
                ).reconcile()
            self.write(
                {"state": "uploaded",
                    "date_uploaded": fields.Date.context_today(self)}
            )
        return True

    def find_draft_moves_linked_to_payments(self):

        payment_ids = self.payment_ids.move_id.mapped('id')

        draft_moves = self.env['account.move'].search([
            ('state', '=', 'draft'),
            ('id', 'in', payment_ids)
        ])

        return draft_moves

    def return_exchange_moves(self):
        exch_moves = []
        for move in self.move_ids:
            for line in move.line_ids:
                if line.matched_credit_ids:
                    for matc_line in line.matched_credit_ids:
                        exch_moves += self.eval_exchange_moves(
                            matc_line, exch_moves)
                if line.matched_debit_ids:
                    for matc_line in line.matched_debit_ids:
                        exch_moves += self.eval_exchange_moves(
                            matc_line, exch_moves)
        exch_moves = self.reconcile_eval_exchange_moves(exch_moves)
        return exch_moves

    def reconcile_eval_exchange_moves(self, exch_moves):
        exch_accounts = self.get_exch_accounts()
        for move in self.move_ids:
            for line in move.line_ids:
                if line.full_reconcile_id:
                    for rline in line.full_reconcile_id.reconciled_line_ids:
                        if rline.move_id not in self.move_ids:
                            for mrline in rline.move_id.line_ids:
                                if mrline.account_id in exch_accounts and \
                                        mrline.move_id.id not in exch_moves:
                                    exch_moves.append(mrline.move_id.id)
        return exch_moves

    def eval_exchange_moves(self, matc_line, exch_moves):
        exch_accounts = self.get_exch_accounts()
        exch_moves = []
        if matc_line.credit_move_id:
            if (matc_line.credit_move_id.move_id not in self.move_ids):
                for line in matc_line.credit_move_id.move_id.line_ids:
                    if line.account_id in exch_accounts and \
                            line.move_id not in exch_moves:
                        exch_moves.append(line.move_id.id)
        if matc_line.debit_move_id:
            if (matc_line.debit_move_id.move_id not in self.move_ids):
                for line in matc_line.debit_move_id.move_id.line_ids:
                    if line.account_id in exch_accounts and \
                            line.move_id not in exch_moves:
                        exch_moves.append(line.move_id.id)
        return exch_moves

    def get_exch_accounts(self):
        return [
            self.journal_id.company_id.expense_currency_exchange_account_id,
            self.journal_id.company_id.income_currency_exchange_account_id
        ]

    def returns_number_of_exch_moves(self):
        return len(self.return_exchange_moves())

    def action_move_journal_line(self):
        self.ensure_one()
        action = self.env.ref(
            'account.action_move_journal_line').sudo().read()[0]
        if self.move_count == 1:
            action.update(
                {
                    'view_mode': 'form,list,kanban',
                    'views': False,
                    'view_id': False,
                    'res_id': self.move_ids[0].id,
                }
            )
        else:
            action['domain'] = [
                ('id', 'in', self.move_ids.ids + self.return_exchange_moves())
            ]
        ctx = self.env.context.copy()
        ctx.update({'search_default_misc_filter': 0})
        action['context'] = ctx
        return action

    def _prepare_move_line_offsetting_account(
        self, amount_company_currency, amount_payment_currency, bank_lines
    ):
        vals = {}
        payment_method = self.payment_mode_id.payment_method_id
        company_id = self.journal_id.company_id
        account_id = False
        if self.payment_type == 'inbound':
            if company_id.charges_from_the_journal:
                account_id = self.journal_id.default_account_id.id
            else:
                account_id = (
                    self.journal_id.inbound_payment_method_line_ids.filtered(
                        lambda x: x.payment_method_id == payment_method
                    ).payment_account_id.id or
                    company_id.account_journal_payment_debit_account_id.id
                )
        elif self.payment_type == 'outbound':
            if company_id.payments_from_the_journal:
                account_id = self.journal_id.default_account_id.id
            else:
                account_id = (
                    self.journal_id.outbound_payment_method_line_ids.filtered(
                        lambda x: x.payment_method_id == payment_method
                    ).payment_account_id.id or
                    company_id.account_journal_payment_credit_account_id.id
                )

        partner_id = False
        for index, bank_line in enumerate(bank_lines):
            if index == 0:
                partner_id = bank_line.payment_line_ids[0].partner_id.id
            elif bank_line.payment_line_ids[0].partner_id.id != partner_id:
                # we have different partners in the grouped move
                partner_id = False
                break
        vals.update(
            {
                'partner_id': partner_id,
                'account_id': account_id,
                'credit': (
                    self.payment_type == 'outbound' and
                    amount_company_currency or 0.0
                ),
                'debit': (
                    self.payment_type == 'inbound' and
                    amount_company_currency or 0.0
                ),
            }
        )
        if bank_lines[0].currency_id != bank_lines[0].company_currency_id:
            sign = self.payment_type == 'outbound' and -1 or 1
            vals.update(
                {
                    'currency_id': bank_lines[0].currency_id.id,
                    'amount_currency': amount_payment_currency * sign,
                }
            )
        return vals

    def get_date_scheduled(self):
        self.ensure_one()
        date_scheduled = False
        if self.date_prefered == 'now':
            date_scheduled =  self.create_date
        elif self.date_prefered == 'due':
            lines = self.payment_line_ids.filtered(
                lambda x: x.ml_maturity_date
            )
            date_scheduled =  max(lines.mapped("ml_maturity_date"), default=False)

        elif self.date_prefered == 'fixed':
            date_scheduled = self.date_scheduled

        return date_scheduled.strftime('%d-%m-%Y') if date_scheduled else date_scheduled

    def action_send_to_suppliers(self):
        report_action = self.env.ref(
            "account_payment_order_baseline.action_print_payment_order_supplier_group",
            raise_if_not_found=False,
        )
        if not report_action:
            raise UserError(
                _(
                    "No se encontró el reporte consolidado de orden de pago. "
                    "Verifique el módulo account_payment_order_baseline."
                )
            )

        for order in self:
            payment_lines = order.payment_line_ids.filtered(lambda line: line.partner_id)
            if not payment_lines:
                raise UserError(
                    _("La orden de pago %s no tiene líneas con proveedor.") % order.display_name
                )

            partner_lines = {}
            for line in payment_lines:
                partner = line.partner_id.commercial_partner_id
                if partner.id not in partner_lines:
                    partner_lines[partner.id] = {
                        "partner": partner,
                        "lines": self.env["account.payment.line"],
                    }
                partner_lines[partner.id]["lines"] |= line

            sent_count = 0
            skipped_partners = []

            for partner_data in partner_lines.values():
                partner = partner_data["partner"]
                lines = partner_data["lines"].sorted(
                    key=lambda line: (line.date or False, line.id)
                )

                email_to = ",".join(tools.email_split(partner.email or ""))
                if not email_to:
                    skipped_partners.append(partner.display_name)
                    continue

                pdf_content, _content_type = self.env["ir.actions.report"].sudo()._render_qweb_pdf(
                    report_action.id,
                    res_ids=lines.ids,
                )
                filename = "%s-%s.pdf" % (
                    (order.name or "OrdenPago").replace("/", "_"),
                    (partner.display_name or "Proveedor").replace("/", "_"),
                )
                attachment = self.env["ir.attachment"].sudo().create(
                    {
                        "name": filename,
                        "type": "binary",
                        "datas": base64.b64encode(pdf_content),
                        "mimetype": "application/pdf",
                        "res_model": order._name,
                        "res_id": order.id,
                    }
                )

                body_html = _(
                    "<p>Estimado proveedor,</p>"
                    "<p>Adjuntamos comprobante(s) de pago correspondiente(s) a la orden "
                    "<strong>%(order)s</strong>, consolidado con sus facturas pagadas.</p>"
                    "<p>Atentamente.</p>"
                ) % {"order": order.name or order.display_name}

                mail_values = {
                    "subject": _("Comprobante(s) de pago - %s") % (order.name or order.display_name),
                    "body_html": body_html,
                    "email_to": email_to,
                    "email_from": order.company_id.email or self.env.user.email,
                    "model": order._name,
                    "res_id": order.id,
                    "attachment_ids": [(6, 0, [attachment.id])],
                    "auto_delete": False,
                }
                self.env["mail.mail"].sudo().create(mail_values).send()
                sent_count += 1

            summary = _(
                "Envío masivo de comprobantes completado. Proveedores notificados: %(sent)s."
            ) % {"sent": sent_count}
            if skipped_partners:
                summary += _(
                    "<br/>Sin correo configurado: %(partners)s"
                ) % {"partners": ", ".join(skipped_partners)}
            order.message_post(body=summary)

            if sent_count == 0:
                _logger.warning(
                    "No se enviaron comprobantes para la orden %s. "
                    "Todos los proveedores estaban sin correo.",
                    order.display_name,
                )
                missing_partners = ", ".join(skipped_partners) if skipped_partners else _("(sin detalle)")
                raise UserError(
                    _(
                        "No fue posible enviar correos porque ningún proveedor tiene "
                        "correo electrónico válido configurado.\n\n"
                        "Proveedores sin correo: %s"
                    )
                    % missing_partners
                )

        return True
