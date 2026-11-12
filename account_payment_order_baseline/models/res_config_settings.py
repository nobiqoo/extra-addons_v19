# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    restrict_paid_document_unreconcile = fields.Boolean(
        related='company_id.restrict_paid_document_unreconcile',
        readonly=False,
    )
