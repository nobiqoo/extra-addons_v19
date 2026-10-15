# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import date


class CertificatePeriod(models.Model):
    _name = "certificate.period"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Certificate period"
    _order = 'create_date desc'

    name = fields.Char(string="Name", required=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string="Date from", required=True)
    date_to = fields.Date(string="Date to", required=True)
    periodicity = fields.Selection(
        selection=[
            ('monthly', 'Monthly'),
            ('bimonthly', 'Bimonthly'),
            ('quarterly', 'Quarterly'),
            ('biannual', 'Biannual'),
            ('annual', 'Annual')
        ],
        string="Periodicity",
        required=True
    )

    def valitade_dates(self, date_from, date_to):
        if date_from >= date_to:
            raise ValidationError(
                _('The date end could be greater than init date.'))
        if date_from.year != date_to.year:
            raise ValidationError(
                _('The year of date end and init date must be the same.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super(CertificatePeriod, self).create(vals_list)
        for record in records:
            self.valitade_dates(record.date_from, record.date_to)
        return records

    def write(self, vals):
        res = super(CertificatePeriod, self).write(vals)
        for record in self:
            self.valitade_dates(record.date_from, record.date_to)
        return res
