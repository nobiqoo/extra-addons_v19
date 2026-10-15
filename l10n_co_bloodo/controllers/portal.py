# -*- coding: utf-8 -*-

from odoo.addons.account.controllers.portal import PortalAccount

class ExtendPortalAccount(PortalAccount):

    def _show_report(self, model, report_type, report_ref, download=False):
        if report_ref == 'account.account_invoices':
            report_id = model.company_id.report_template
            if report_id:
                report_ref = report_id.get_external_id()[report_id.id]
        return super(ExtendPortalAccount, self)._show_report(model, report_type, report_ref, download)
