# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.addons.web.controllers.utils import clean_action
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    analytic_account_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Analytic Account',
    )

    @api.model_create_multi
    def create(self, vals_list):
        reses = super(StockPicking, self).create(vals_list)
        for res in reses:
            if res.company_id.note_sale_to_picking and res.origin:
                sale_id = self.env['sale.order'].search(
                    [('name', '=', res.origin)],
                    limit=1
                )
                if sale_id:
                    res.note = res.note and '%s\n%s' % (
                        res.note, sale_id.note or '') or \
                        sale_id.note
        return reses

    def _post_put_in_pack_hook(self, package_id):
        res = super()._post_put_in_pack_hook(package_id)
        if package_id and self.picking_type_id.auto_print_package_label:
            if self.picking_type_id.package_label_to_print == 'pdf':
                report_id = self.picking_type_id.package_label_report_template_pdf or self.env.ref("stock.action_report_quant_package_barcode_small")
                action = report_id.report_action(package_id.id, config=False)
            elif self.picking_type_id.package_label_to_print == 'zpl':
                report_id = self.picking_type_id.package_label_report_template_zpl or self.env.ref("stock.label_package_template")
                action = report_id.report_action(package_id.id, config=False)
            if action:
                action.update({'close_on_report_download': True})
                clean_action(action, self.env)
                return action
        return res

    def button_validate(self):
        if self.picking_type_id.code != 'incoming' or not self.company_id.validate_incoming_receptions:
            pass
        else:
            if self.env.user not in self.picking_type_id.warehouse_id.user_ids:
                raise UserError(_("You don't have permissions to validate incoming shipments in this warehouse."))

        res = super().button_validate()
        if res is not True:
            return res

        for picking in self:
            if not picking.env.company.create_invoices_from_picking or picking.picking_type_code != 'outgoing':
                continue

            sale_order = picking.sale_id
            if not sale_order or sale_order.invoice_status != 'to invoice':
                continue

            # Same check _create_invoices() runs internally before deciding
            # whether an order is invoiceable (sale/models/sale_order.py); we
            # repeat it here so a picking with nothing real to bill never
            # gets a wizard/invoice created for it in the first place.
            invoiceable_lines = sale_order._get_invoiceable_lines(final=True)
            if not any(not line.display_type for line in invoiceable_lines):
                _logger.info(
                    "Skipping automatic invoice for picking %s: sale order "
                    "%s has no invoiceable product lines yet (only notes/"
                    "sections, or nothing left to bill from this delivery).",
                    picking.name, sale_order.name)
                continue

            if sale_order.partner_id.invoice_manually_from_picking:
                _logger.info(
                    "Skipping automatic invoice for picking %s: partner %s "
                    "is excluded from automatic invoicing.",
                    picking.name, sale_order.partner_id.display_name)
                continue

            journal_id = sale_order.warehouse_id.journal_id
            if not journal_id:
                raise UserError(
                    _("Please set a journal in the warehouse configuration."))

            wizard = picking.env['sale.advance.payment.inv'].with_context(
                active_ids=sale_order.ids,
                active_id=sale_order.id
            ).create({
                'advance_payment_method': 'delivered'
            })
            invoices = wizard._create_invoices(sale_order)
            if invoices:
                invoices.write({
                    "journal_id": journal_id.id,
                    "narration": sale_order.note or '',
                })
                invoices.with_context(fe_send_later=True).action_post()

            invoice_links = []
            for inv in invoices:
                link = f'{inv.name}'
                invoice_links.append(link)

            invoice_list = ', '.join(invoice_links)
            message = _(
                "Invoice(s) %s automatically created when validating this picking.") % invoice_list

            picking.message_post(
                body=message,
                message_type="comment",
                subtype_xmlid="mail.mt_note"
            )

            if sale_order:
                sale_order.message_post(
                    body=_("Invoice(s) %s automatically created from this picking. %s.") % (
                        invoice_list, picking.name),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note"
                )

        return res
