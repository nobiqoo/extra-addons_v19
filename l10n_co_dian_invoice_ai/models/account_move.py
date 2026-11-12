# -*- coding: utf-8 -*-
import json

from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    ai_document_id = fields.Many2one(
        'dian.document', 'Documento DIAN del agente', copy=False,
        index='btree_not_null', ondelete='set null')
    ai_review_state = fields.Selection(
        [('pending', 'Para revisión'),
         ('confirmed', 'Revisión correcta'),
         ('corrected', 'Corregida por el contador')],
        'Revisión del agente', copy=False, tracking=True)
    ai_explanation = fields.Text('Explicación del agente', copy=False)
    ai_has_pending_note = fields.Boolean(
        'Tiene notas por revisar', compute='_compute_ai_has_pending_note')

    @api.depends('ai_document_id', 'ai_document_id.ai_state')
    def _compute_ai_has_pending_note(self):
        for move in self:
            document = move.ai_document_id
            move.ai_has_pending_note = bool(document) and bool(document.sudo()._ai_pending_notes())

    def _ai_close_review_activities(self, feedback):
        summaries = (_('Revisar factura del agente'), _('Para revisión: impuesto ajustado por el agente'))
        self.activity_ids.filtered(lambda a: a.summary in summaries).action_feedback(feedback=feedback)

    def action_ai_review_confirm(self):
        """The accountant confirms what the agent adjusted: it becomes a learned rule (CA-04b)."""
        self.check_access('write')
        for move in self.filtered(lambda m: m.ai_review_state == 'pending'):
            rules = self.env['dian.ai.rule'].search([('move_id', '=', move.id), ('state', '=', 'proposed')])
            rules.write({'state': 'learned', 'user_id': self.env.user.id})
            move.ai_review_state = 'confirmed'
            if move.ai_document_id.ai_state == 'review':
                move.ai_document_id.ai_state = 'posted'
            move._ai_close_review_activities(_('Revisión correcta'))
        return True

    def action_ai_explain(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Explicar al agente'),
            'res_model': 'dian.ai.explain.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

    def action_ai_open_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dian.document',
            'res_id': self.ai_document_id.id,
            'view_mode': 'form',
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _ai_correction_snapshot(self):
        return {
            line.id: {
                'tax': line.tax_ids,
                'account': line.account_id,
                'analytic': json.dumps(line.analytic_distribution or {}, sort_keys=True),
            } for line in self
        }

    def write(self, vals):
        # The agent runs with dian_ai_document_id: only human corrections are precedents
        lines = self.browse()
        if {'tax_ids', 'account_id', 'analytic_distribution'} & set(vals) \
                and not self.env.context.get('dian_ai_document_id'):
            lines = self.filtered(lambda line: line.display_type == 'product' and line.move_id.ai_document_id)
        before = lines._ai_correction_snapshot()
        result = super().write(vals)
        if lines:
            lines._ai_record_corrections(before)
        return result

    def _ai_record_corrections(self, before):
        """Register what the accountant changed on an invoice of the agent (CA-07)."""
        rules = self.env['dian.ai.rule'].sudo()
        for line in self:
            previous = before[line.id]
            base = {
                'company_id': line.company_id.id,
                'origin': 'correction',
                'scope': 'partner_product',
                'partner_id': line.move_id.partner_id.id,
                'product_id': line.product_id.id,
                'user_id': self.env.user.id,
                'move_id': line.move_id.id,
            }
            vals_list = []
            for operation, taxes in (('add', line.tax_ids - previous['tax']),
                                     ('remove', previous['tax'] - line.tax_ids)):
                vals_list += [{
                    **base,
                    'field_name': 'tax',
                    'operation': operation,
                    'tax_id': tax.id,
                    'original_value': ', '.join(previous['tax'].mapped('name')),
                    'corrected_value': ', '.join(line.tax_ids.mapped('name')),
                } for tax in taxes]
            if line.account_id != previous['account']:
                vals_list.append({
                    **base,
                    'field_name': 'account',
                    'original_value': previous['account'].display_name,
                    'corrected_value': line.account_id.display_name,
                })
            analytic = json.dumps(line.analytic_distribution or {}, sort_keys=True)
            if analytic != previous['analytic']:
                vals_list.append({
                    **base,
                    'field_name': 'analytic',
                    'original_value': previous['analytic'],
                    'corrected_value': analytic,
                })
            if not vals_list:
                continue
            rules.create(vals_list)
            move = line.move_id.sudo()
            if move.ai_review_state == 'pending':
                rules.search([('move_id', '=', move.id), ('state', '=', 'proposed')]).write({'state': 'rejected'})
                move.ai_review_state = 'corrected'
                if move.ai_document_id.ai_state == 'review':
                    move.ai_document_id.ai_state = 'posted'
                move._ai_close_review_activities(_('Corregida por el contador'))
