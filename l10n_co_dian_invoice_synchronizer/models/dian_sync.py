# -*- coding: utf-8 -*-

import html as html_lib

from odoo import _, api, fields, models


class DianSync(models.Model):
    _name = 'dian.sync'
    _description = 'DIAN Invoice Synchronization'
    _order = 'sync_date desc'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
    )
    name = fields.Char(
        string='Name',
        required=True,
        readonly=True,
        copy=False,
        index=True,
    )
    sync_date = fields.Datetime(
        'Sync Date',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    sync_duration_seconds = fields.Float(
        'Sync Duration (s)',
        readonly=True,
        help='Time in seconds that the synchronization took (fetch_invoices).',
    )
    sync_period = fields.Char(
        'Synchronized Period',
        readonly=True,
        help='Year, month and week that were synchronized (e.g. 2025 - February - Week 2).',
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True,
        ondelete='restrict',
        readonly=True,
    )
    document_ids = fields.One2many(
        'dian.document',
        'sync_id',
        string='Documents',
    )
    dian_records_filtered = fields.Integer(
        'DIAN Records Filtered',
        readonly=True,
        help='Total count reported by DIAN for the date range (recordsFiltered from API).',
    )
    discarded_cufes = fields.Text(
        'Discarded CUFEs',
        help='One CUFE per line (documents already present in the date range).',
    )
    discarded_html = fields.Html(
        string='Discarded Documents',
        compute='_compute_discarded_html',
        sanitize=False,
    )
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count',
    )
    already_in_system_count = fields.Integer(
        string='Already in System',
        compute='_compute_already_in_system_count',
        help='Documents skipped because they were already imported for this date range.',
    )
    application_response_count = fields.Integer(
        string='Application Responses',
        readonly=True,
        help='Documents of type "Application response" received from DIAN and excluded from import.',
    )
    mapping_error_count = fields.Integer(
        'Mapping Errors',
        readonly=True,
        help='Documents received from DIAN that could not be mapped into a dian.document record '
             '(e.g. missing mandatory fields) and were therefore not imported.',
    )
    mapping_errors_text = fields.Text(
        'Mapping Errors Detail',
        help='One entry per line, format "cufe|name|error".',
    )
    mapping_errors_html = fields.Html(
        string='Mapping Errors',
        compute='_compute_mapping_errors_html',
        sanitize=False,
    )
    unaccounted_count = fields.Integer(
        'Unaccounted Records',
        compute='_compute_unaccounted_count',
        help='dian_records_filtered minus (document_count + already_in_system_count + '
             'application_response_count + mapping_error_count). Should always be 0 - a non-zero '
             'value means some documents reported by DIAN were lost somewhere in the pipeline '
             'without being counted, and is a good candidate for an automated alert.',
    )
    error_summary_html = fields.Html(
        string='Error Summary',
        compute='_compute_error_summary_html',
        sanitize=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                sync_date = vals.get('sync_date') or fields.Datetime.now(self)
                if isinstance(sync_date, str):
                    sync_date = fields.Datetime.from_string(sync_date)
                seq_date = (
                    sync_date.date()
                    if sync_date and hasattr(sync_date, 'date')
                    else fields.Date.context_today(self)
                )
                vals['name'] = self.env['ir.sequence'].with_context(
                    ir_sequence_date=seq_date
                ).next_by_code('dian.sync', sequence_date=seq_date)
        return super().create(vals_list)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    @api.depends('discarded_cufes')
    def _compute_already_in_system_count(self):
        for record in self:
            if not record.discarded_cufes:
                record.already_in_system_count = 0
            else:
                record.already_in_system_count = len(
                    [x for x in record.discarded_cufes.splitlines() if x.strip()]
                )

    @api.depends('discarded_cufes')
    def _compute_discarded_html(self):
        for record in self:
            if not record.discarded_cufes:
                record.discarded_html = '''
                    <div style="text-align: center; color: #6c757d; padding: 2rem;">
                        <span class="fa fa-check-circle" style="font-size: 2rem; display: block; margin-bottom: 0.5rem; color: #28a745;"/>
                        <p style="margin: 0;">%s</p>
                    </div>
                ''' % (_('No documents were discarded.'),)
                continue
            cufes = [x.strip() for x in record.discarded_cufes.splitlines() if x.strip()]
            items = ''.join(
                '<li style="padding: 0.6rem 1rem; border-bottom: 1px solid #eee; '
                'display: flex; align-items: center; gap: 0.75rem; font-family: monospace; font-size: 0.9rem;">'
                '<span style="background: #e9ecef; color: #495057; padding: 0.25rem 0.5rem; '
                'border-radius: 4px; word-break: break-all;">%s</span>'
                '<span style="color: #6c757d; font-size: 0.85rem; font-style: normal;">%s</span>'
                '</li>' % (cufe, _('Already in system for this date range'))
                for cufe in cufes
            )
            record.discarded_html = '''
                <div style="padding: 0 0 1rem 0;">
                    <p style="color: #6c757d; margin-bottom: 0.75rem; font-size: 0.95rem;">
                        <span class="fa fa-info-circle"/> %s
                    </p>
                    <ul style="list-style: none; margin: 0; padding: 0; border: 1px solid #dee2e6; border-radius: 6px; max-width: 720px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); overflow: hidden;">
                        %s
                    </ul>
                </div>
            ''' % (_('The following documents were not imported because they already exist for the selected period.'), items)

    @api.depends('dian_records_filtered', 'document_count', 'already_in_system_count', 'application_response_count', 'mapping_error_count')
    def _compute_unaccounted_count(self):
        for record in self:
            record.unaccounted_count = record.dian_records_filtered - (
                record.document_count + record.already_in_system_count
                + record.application_response_count + record.mapping_error_count
            )

    @api.depends('mapping_errors_text')
    def _compute_mapping_errors_html(self):
        for record in self:
            if not record.mapping_errors_text:
                record.mapping_errors_html = '''
                    <div style="text-align: center; color: #6c757d; padding: 2rem;">
                        <span class="fa fa-check-circle" style="font-size: 2rem; display: block; margin-bottom: 0.5rem; color: #28a745;"/>
                        <p style="margin: 0;">%s</p>
                    </div>
                ''' % (_('No mapping errors.'),)
                continue
            items = []
            for line in record.mapping_errors_text.splitlines():
                if not line.strip():
                    continue
                cufe, name, error = (line.split('|', 2) + ['', '', ''])[:3]
                cufe_display = html_lib.escape(cufe)
                name_display = html_lib.escape(name)
                error_display = html_lib.escape(error)
                items.append('''
                    <li style="padding: 0.75rem 1rem; border-bottom: 1px solid #f5e6e6; background: #fef8f8;
                        display: flex; flex-direction: column; gap: 0.35rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                            <span style="background: #dc3545; color: #fff; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">%s</span>
                            <span style="font-weight: 600; color: #333;">%s</span>
                            <span style="font-family: monospace; font-size: 0.8rem; color: #6c757d; word-break: break-all;">%s</span>
                        </div>
                        <div style="font-size: 0.9rem; color: #721c24; line-height: 1.4;">%s</div>
                    </li>
                ''' % (_('Not mapped'), name_display or '—', cufe_display or '—', error_display))
            record.mapping_errors_html = '''
                <div style="padding: 0 0 1rem 0;">
                    <p style="color: #856404; margin-bottom: 0.75rem; font-size: 0.95rem;">
                        <span class="fa fa-exclamation-triangle"/> %s
                    </p>
                    <ul style="list-style: none; margin: 0; padding: 0; border: 1px solid #f5c6cb; border-radius: 6px; max-width: 720px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); overflow: hidden; background: #fff;">
                        %s
                    </ul>
                </div>
            ''' % (
                _('The following documents were received from DIAN but could not be mapped and were not imported.'),
                ''.join(items),
            )

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
