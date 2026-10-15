# -*- coding: utf-8 -*-

import calendar
import time
from datetime import datetime, date

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DianInvoiceSynchronizer(models.TransientModel):
    _name = 'dian.invoice.synchronizer'
    _description = 'DIAN Invoice Synchronizer'

    token_url = fields.Char('DIAN Token URL', required=True)
    year = fields.Selection(
        selection='_get_year_selection',
        string='Year',
        required=True,
        default=lambda self: self._get_current_year(),
    )
    month = fields.Selection(
        selection=[
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
        ],
        string='Month',
        required=True,
    )
    week = fields.Selection(
        selection=[
            ('1', 'Week 1'),
            ('2', 'Week 2'),
            ('3', 'Week 3'),
            ('4', 'Week 4'),
            ('5', 'Week 5'),
        ],
        string='Week',
        required=True,
        help="Week 1: Days 1-6 | Week 2: Days 7-12 | Week 3: Days 13-18 | Week 4: Days 19-24 | Week 5: Days 25 to end of month",
    )
    start_date = fields.Date('Start Date', compute='_compute_date_range', store=False)
    end_date = fields.Date('End Date', compute='_compute_date_range', store=False)

    # --- Selection helpers (UI) ---
    @api.model
    def _get_current_year(self):
        return str(datetime.now().year)

    @api.model
    def _get_year_selection(self):
        current_year = datetime.now().year
        previous_year = current_year - 1
        return [
            (str(previous_year), str(previous_year)),
            (str(current_year), str(current_year)),
        ]

    @api.depends('year', 'month', 'week')
    def _compute_date_range(self):
        """Calculate start_date and end_date based on year, month, and week."""
        for record in self:
            if not record.year or not record.month or not record.week:
                record.start_date = False
                record.end_date = False
                continue
            try:
                year = int(record.year)
                month = int(record.month)
                week = int(record.week)
                if week == 1:
                    start_day, end_day = 1, 6
                elif week == 2:
                    start_day, end_day = 7, 12
                elif week == 3:
                    start_day, end_day = 13, 18
                elif week == 4:
                    start_day, end_day = 19, 24
                else:
                    start_day = 25
                    end_day = calendar.monthrange(year, month)[1]
                record.start_date = date(year, month, start_day)
                record.end_date = date(year, month, end_day)
            except (ValueError, TypeError):
                record.start_date = False
                record.end_date = False

    def _validate_selection_fields(self):
        """Validate that year, month, and week are selected and dates are valid."""
        if not self.year or not self.month or not self.week:
            raise UserError(_("Please select year, month, and week before synchronizing."))
        self._compute_date_range()
        if not self.start_date or not self.end_date:
            raise UserError(_("Invalid date range. Please check your year, month, and week selection."))

    def sync(self):
        """Validate wizard input and delegate to DIAN API client."""
        self.ensure_one()
        self._validate_selection_fields()

        client = self.env['dian.api.client']

        t0 = time.perf_counter()
        documents_received, discarded, records_filtered, application_response_count, mapping_errors = client.fetch_invoices(
            self.token_url, self.start_date, self.end_date, self.env.company
        )
        sync_duration_seconds = time.perf_counter() - t0

        company_id = self.env.company.id
        for vals in documents_received:
            vals['company_id'] = company_id

        month_labels = dict(self._fields['month']._description_selection(self.env))
        week_labels = dict(self._fields['week']._description_selection(self.env))
        sync_period = f"{self.year} - {month_labels[self.month]} - {week_labels[self.week]}"

        sync = self.env['dian.sync'].create({
            'company_id': company_id,
            'user_id': self.env.user.id,
            'sync_duration_seconds': round(sync_duration_seconds, 2),
            'sync_period': sync_period,
            'dian_records_filtered': records_filtered,
            'discarded_cufes': '\n'.join(discarded) if discarded else '',
            'application_response_count': application_response_count,
            'mapping_error_count': len(mapping_errors),
            'mapping_errors_text': '\n'.join(
                '%s|%s|%s' % (e['cufe'], e['name'], e['error']) for e in mapping_errors
            ) if mapping_errors else '',
            'document_ids': [(0, 0, vals) for vals in documents_received],
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Synchronization'),
            'res_model': 'dian.sync',
            'res_id': sync.id,
            'view_mode': 'form',
            'target': 'current',
        }

