# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Maximum number of documents a user can request at once.
XML_FETCH_WIZARD_LIMIT = 100


class DianDocumentXmlFetchWizard(models.TransientModel):
    """
    Request the XML of the selected dian.document records.

    It does not call DIAN: it queues the documents as prioritary and triggers the
    fetch cron (dian.document._cron_fetch_xml), the only process that fetches XML.
    Documents the cron is processing, already loaded, or of a company without
    direct e-invoicing are left out.
    """
    _name = 'dian.document.xml.fetch.wizard'
    _description = 'Fetch XML of DIAN documents'

    document_ids = fields.Many2many(
        'dian.document',
        string='Documents',
        readonly=True,
    )
    to_queue_count = fields.Integer(compute='_compute_counts')
    processing_count = fields.Integer(compute='_compute_counts')
    done_count = fields.Integer(compute='_compute_counts')
    not_allowed_count = fields.Integer(compute='_compute_counts')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'dian.document':
            active_ids = self.env.context.get('active_ids') or []
            if len(active_ids) > XML_FETCH_WIZARD_LIMIT:
                raise UserError(_(
                    "You can request the XML of at most %(limit)s documents at once "
                    "(%(count)s selected).",
                    limit=XML_FETCH_WIZARD_LIMIT, count=len(active_ids)))
            res['document_ids'] = [(6, 0, active_ids)]
        return res

    def _split_documents(self):
        """Return (to_queue, processing, done, not_allowed) recordsets."""
        self.ensure_one()
        documents = self.document_ids
        not_allowed = documents.filtered(lambda d: d.company_id.type_einvoicing != 'edi_dir')
        allowed = documents - not_allowed
        processing = allowed.filtered(lambda d: d.xml_state == 'processing')
        done = allowed.filtered(lambda d: d.xml_state == 'done')
        return allowed - processing - done, processing, done, not_allowed

    @api.depends('document_ids', 'document_ids.xml_state')
    def _compute_counts(self):
        for wizard in self:
            to_queue, processing, done, not_allowed = wizard._split_documents()
            wizard.to_queue_count = len(to_queue)
            wizard.processing_count = len(processing)
            wizard.done_count = len(done)
            wizard.not_allowed_count = len(not_allowed)

    def action_confirm(self):
        self.ensure_one()
        if len(self.document_ids) > XML_FETCH_WIZARD_LIMIT:
            raise UserError(_(
                "You can request the XML of at most %s documents at once.",
                XML_FETCH_WIZARD_LIMIT))
        to_queue = self._split_documents()[0]
        queued = self.env['dian.document']
        if to_queue:
            # Re-check the state in the database while locking the rows: the cron may
            # have claimed some of them since the wizard was opened. Rows the cron holds
            # locked are skipped instead of waited for.
            self.env['dian.document'].flush_model(['xml_state'])
            self.env.cr.execute("""
                SELECT id FROM dian_document
                 WHERE id IN %s AND xml_state IN ('pending', 'error')
                   FOR UPDATE SKIP LOCKED
            """, [tuple(to_queue.ids)])
            queued = to_queue.browse([row[0] for row in self.env.cr.fetchall()])
            to_queue.invalidate_recordset(['xml_state'])
        if queued:
            queued.write({
                'xml_state': 'pending',
                'xml_attempts': 0,
                'xml_priority': True,
                'xml_query_error_message': False,
            })
            self.env['dian.document']._xml_trigger_cron()
        skipped = len(self.document_ids) - len(queued)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('XML request'),
                'message': _(
                    "%(queued)s document(s) queued to fetch their XML, %(skipped)s skipped "
                    "(already loaded, being processed or company without direct e-invoicing).",
                    queued=len(queued), skipped=skipped),
                'type': 'success' if queued else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
