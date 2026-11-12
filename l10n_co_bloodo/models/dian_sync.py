# -*- coding: utf-8 -*-

import html as html_lib

from odoo import _, api, fields, models


class DianSync(models.Model):
    _inherit = 'dian.sync'

    xml_state = fields.Selection(
        selection=[
            ('pending', 'Pending XML'),
            ('done', 'XML loaded'),
            ('error', 'Error'),
        ],
        string='XML Status',
        compute='_compute_xml_state',
        store=True,
        index=True,
        help='Error: at least one document failed to fetch its XML. '
             'Pending XML: at least one document is still waiting for (or processing) its XML. '
             'XML loaded: every document has its XML data.',
    )
    error_summary_html = fields.Html(
        string='Error Summary',
        compute='_compute_error_summary_html',
        sanitize=False,
    )

    @api.depends('document_ids.xml_state')
    def _compute_xml_state(self):
        for record in self:
            states = set(record.document_ids.mapped('xml_state'))
            if 'error' in states:
                record.xml_state = 'error'
            elif states & {'pending', 'processing'}:
                record.xml_state = 'pending'
            else:
                record.xml_state = 'done'

    @api.depends('document_ids', 'document_ids.xml_query_error_message')
    def _compute_error_summary_html(self):
        for record in self:
            docs_with_errors = [
                doc for doc in record.document_ids
                if doc.xml_query_error_message and doc.xml_query_error_message.strip()
            ]
            if not docs_with_errors:
                record.error_summary_html = '''
                    <div style="text-align: center; color: #6c757d; padding: 2rem;">
                        <span class="fa fa-check-circle" style="font-size: 2rem; display: block; margin-bottom: 0.5rem; color: #28a745;"/>
                        <p style="margin: 0;">%s</p>
                    </div>
                ''' % (_('No errors during synchronization.'),)
                continue
            items = []
            for doc in docs_with_errors:
                name_display = html_lib.escape((doc.name or doc.cufe or '—'))
                cufe_display = html_lib.escape((doc.cufe or ''))
                msg_display = html_lib.escape((doc.xml_query_error_message or '').strip())
                items.append('''
                    <li style="padding: 0.75rem 1rem; border-bottom: 1px solid #f5e6e6; background: #fef8f8;
                        display: flex; flex-direction: column; gap: 0.35rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                            <span style="background: #dc3545; color: #fff; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">Error</span>
                            <span style="font-weight: 600; color: #333;">%s</span>
                            <span style="font-family: monospace; font-size: 0.8rem; color: #6c757d; word-break: break-all;">%s</span>
                        </div>
                        <div style="font-size: 0.9rem; color: #721c24; line-height: 1.4;">%s</div>
                    </li>
                ''' % (name_display, cufe_display, msg_display))
            _msg_errors_intro = _(
                "The following documents had errors while fetching or parsing XML. Review the messages below."
            )
            record.error_summary_html = '''
                <div style="padding: 0 0 1rem 0;">
                    <p style="color: #856404; margin-bottom: 0.75rem; font-size: 0.95rem;">
                        <span class="fa fa-exclamation-triangle"/> %s
                    </p>
                    <ul style="list-style: none; margin: 0; padding: 0; border: 1px solid #f5c6cb; border-radius: 6px; max-width: 720px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); overflow: hidden; background: #fff;">
                        %s
                    </ul>
                </div>
            ''' % (_msg_errors_intro, ''.join(items))
