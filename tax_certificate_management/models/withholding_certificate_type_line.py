# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class WithholdingCertificateTypeLine(models.Model):
    _name = "withholding.certificate.type.line"
    _description = "Withholding certificate type line"
    _order = 'create_date desc'

    tax_account = fields.Many2one(
        'account.account', string='Tax account', required=True)
    tax = fields.Many2one('account.tax', string="Tax", required=True)
    percentage = fields.Float(string='Percentage', required=True)
    type_id = fields.Many2one(
        'withholding.certificate.type', string="Certificate type", required=True)
    city_id = fields.Many2one('res.city', string="City (ICA Apply)")

    @api.onchange('tax')
    def onchange_tax(self):
        self.percentage = abs(self.tax.amount)
