# -*- coding: utf-8 -*-

from odoo import _, models


class DianDocument(models.Model):
    _inherit = 'dian.document'

    def action_match_account_moves(self):
        """
        Match selected records with their supplier invoice (account.move.uuid_ei_ref,
        defined in this module) of the same company. Returns a notification.
        """
        already_linked = self.filtered(lambda d: d.move_id)
        to_process = self - already_linked
        cufes = to_process.mapped('cufe')
        # Only invoices of the document's own company
        moves = self.env['account.move'].search([
            ('uuid_ei_ref', 'in', cufes),
            ('company_id', 'in', to_process.company_id.ids),
        ])
        cufe_to_move = {(m.uuid_ei_ref, m.company_id.id): m for m in moves if m.uuid_ei_ref}
        matched = 0
        for doc in to_process:
            move = cufe_to_move.get((doc.cufe, doc.company_id.id))
            if move:
                doc.move_id = move
                matched += 1
        not_matched = len(to_process) - matched
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Matching complete'),
                'message': _(
                    '%d documents linked, %d not matched, %d already had an invoice.'
                ) % (matched, not_matched, len(already_linked)),
                'type': 'success' if matched > 0 else 'warning',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
