# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ocr_opening_journal_id = fields.Many2one(
        related='company_id.ocr_opening_journal_id', readonly=False)
    ocr_advance_account_prefix = fields.Char(
        related='company_id.ocr_advance_account_prefix', readonly=False)
    ocr_cartera_extra_account_ids = fields.Many2many(
        related='company_id.ocr_cartera_extra_account_ids', readonly=False)
    ocr_collection_account_prefix = fields.Char(
        related='company_id.ocr_collection_account_prefix', readonly=False)
    ocr_collection_excluded_accounts = fields.Char(
        related='company_id.ocr_collection_excluded_accounts', readonly=False)
    ocr_collection_excluded_journal_codes = fields.Char(
        related='company_id.ocr_collection_excluded_journal_codes',
        readonly=False)
    ocr_datacredito_excluded_accounts = fields.Char(
        related='company_id.ocr_datacredito_excluded_accounts', readonly=False)
    ocr_datacredito_excluded_prefixes = fields.Char(
        related='company_id.ocr_datacredito_excluded_prefixes', readonly=False)
    ocr_excluded_partner_vats = fields.Char(
        related='company_id.ocr_excluded_partner_vats', readonly=False)
