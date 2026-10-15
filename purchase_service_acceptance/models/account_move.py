# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    service_acceptance_ids = fields.Many2many(
        comodel_name='purchase.service.acceptance',
        string='Service Acceptances',
        compute='_compute_service_acceptance_ids',
    )
    service_acceptance_count = fields.Integer(
        string='Service Acceptance Count',
        compute='_compute_service_acceptance_ids',
    )

    @api.depends('line_ids.purchase_line_id')
    def _compute_service_acceptance_ids(self):
        """Reverse-traceability: from a vendor bill or credit note, find the
        Service Acceptance(s) it relates to -- closing the
        "Factura -> Aceptación" direction that the one-way `invoice_ids`
        field on purchase.service.acceptance doesn't cover on its own.
        Matched directly through the PO line each acceptance line points to
        (`line_ids.purchase_line_id`)."""
        Acceptance = self.env['purchase.service.acceptance'].sudo()
        for move in self:
            po_lines = move.line_ids.purchase_line_id
            acceptances = Acceptance.search([
                ('line_ids.purchase_line_id', 'in', po_lines.ids),
            ]) if po_lines else Acceptance
            move.service_acceptance_ids = acceptances
            move.service_acceptance_count = len(acceptances)

    def action_view_service_acceptances(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Service Acceptances'),
            'res_model': 'purchase.service.acceptance',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.service_acceptance_ids.ids)],
        }
        if len(self.service_acceptance_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.service_acceptance_ids.id
        return action

    def _post(self, soft=True):
        # Final safety net on top of AccountMoveLine's own @api.constrains
        # (which already blocks this the moment a line is saved, even in
        # draft) — cheap to re-check here too, in case lines were touched
        # through some path that skipped the line-level constrain.
        self.invoice_line_ids._check_service_acceptance_over_invoicing()
        return super()._post(soft=soft)
