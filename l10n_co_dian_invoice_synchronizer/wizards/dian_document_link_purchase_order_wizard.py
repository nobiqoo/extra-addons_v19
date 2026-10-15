# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

DIAN_DOCUMENT_LINK_PO_LIMIT = 100


class DianDocumentLinkPurchaseOrderWizard(models.TransientModel):
    _name = 'dian.document.link.purchase.order.wizard'
    _description = 'Link DIAN Documents to Purchase Orders'

    line_ids = fields.One2many(
        'dian.document.link.purchase.order.wizard.line',
        'wizard_id',
        string='Documents',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'line_ids' in fields_list:
            documents = self.env['dian.document'].search(
                [('purchase_id', '=', False)], limit=DIAN_DOCUMENT_LINK_PO_LIMIT
            )
            res['line_ids'] = [
                (0, 0, {'document_id': document.id}) for document in documents
            ]
        return res

    def action_link_purchase_orders(self):
        self.ensure_one()
        linked = 0
        for line in self.line_ids:
            if line.purchase_order_id:
                line.document_id.purchase_id = line.purchase_order_id
                linked += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Purchase orders linked'),
                'message': _('%d purchase order(s) linked.') % linked,
                'type': 'success' if linked > 0 else 'warning',
                'sticky': False,
            },
        }


class DianDocumentLinkPurchaseOrderWizardLine(models.TransientModel):
    _name = 'dian.document.link.purchase.order.wizard.line'
    _description = 'Link DIAN Document to Purchase Order (line)'

    wizard_id = fields.Many2one(
        'dian.document.link.purchase.order.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    document_id = fields.Many2one(
        'dian.document',
        string='Document',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    document_name = fields.Char(
        related='document_id.name',
        string='Document',
        readonly=True,
    )
    company_id = fields.Many2one(
        related='document_id.company_id',
        string='Company',
        readonly=True,
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
    )
