# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons.web.controllers.utils import clean_action
from odoo.exceptions import UserError


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
        return super().button_validate()
