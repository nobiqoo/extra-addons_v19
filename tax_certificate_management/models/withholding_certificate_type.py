# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
import collections


class WithholdingCertificateType(models.Model):
    _name = "withholding.certificate.type"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Withholding certificate type"
    _order = 'create_date desc'

    name = fields.Char(string="Name", required=True)
    company_id = fields.Many2one('res.company', string="Company")
    type = fields.Selection(
        selection=[
            ('certificate', 'Certificate'),
            ('statement', 'Statement')
        ],
        string="Type",
        required=True
    )
    city_generated_id = fields.Many2one(
        'res.city', string="City where it was generated")
    city_paid_id = fields.Many2one('res.city', string="City where it was paid")
    line_ids = fields.One2many(
        'withholding.certificate.type.line', 'type_id', string="Tax lines", required=True)
    title = fields.Char(string="Title", required=True)
    notes = fields.Char(string="Notes")
    ica = fields.Boolean(string="ICA", default=False)
    keep_header_cities = fields.Boolean(string="Keep main cities")

    @api.constrains("line_ids")
    def _check_tax_account_unique(self):
        tax_ids = [line.tax_account.id for line in self.line_ids]
        list_repeated = [item for item, count in collections.Counter(
            tax_ids).items() if count > 1]
        if len(list_repeated) > 0:
            raise ValidationError(
                _('The accounting account cannot be repeated in the lines.'))