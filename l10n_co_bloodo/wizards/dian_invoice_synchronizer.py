# -*- coding: utf-8 -*-

from odoo import models


class DianInvoiceSynchronizer(models.TransientModel):
    _inherit = 'dian.invoice.synchronizer'

    def sync(self):
        """Start fetching the XML of the new documents without waiting for the next cron run."""
        res = super().sync()
        self.env['dian.document']._xml_trigger_cron()
        return res
