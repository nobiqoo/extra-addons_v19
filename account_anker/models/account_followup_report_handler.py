# -*- coding: utf-8 -*-
import base64

from odoo import models
from odoo.tools import file_open


class AccountFollowupReportHandler(models.AbstractModel):
    _inherit = 'account.followup.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        pdf_templates = options['custom_display_config'].setdefault('pdf_export', {})
        pdf_templates['pdf_export_main'] = 'account_anker.pdf_export_followup_anker'

    def get_anker_followup_logo_uri(self):
        # Embed the image so PDF rendering does not depend on the server URL.
        with file_open('account_anker/static/src/img/anker_followup_logo.jpeg', 'rb') as logo_file:
            encoded_logo = base64.b64encode(logo_file.read()).decode('ascii')
        return 'data:image/jpeg;base64,' + encoded_logo
